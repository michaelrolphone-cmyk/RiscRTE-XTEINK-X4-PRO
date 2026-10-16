#!/usr/bin/env python3
"""No network/mutations: exact existing draft resume safety controls."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import test_x4_bootstrap_publication as old
p=old.p
import resume_x4_bootstrap as r
ORIGINAL='a'*40
CURRENT='b'*40


class Api(old.FakeGithub):
    def json(self, endpoint, method='GET', body=None):
        if endpoint.endswith('/releases/17'):
            self.calls.append((method, endpoint, body))
            if method=='PATCH':
                assert body=={'draft':False,'prerelease':True,'make_latest':'false'}
                self.release['draft']=False
            return self.release
        if '/actions/runs/990/' in endpoint:return self.stage_run
        if '/commits/'+ORIGINAL in endpoint:return dict(sha=ORIGINAL,commit=dict(tree=dict(sha='c'*40)))
        if '/contents/'+r.WORKFLOW+'?' in endpoint:return dict(type='file',encoding='base64',path=r.WORKFLOW,content=base64.b64encode(b'workflow').decode())
        return super().json(endpoint,method,body)
    def pages(self,endpoint,field=None):
        if '/actions/runs/990/' in endpoint:return self.stage_jobs if endpoint.endswith('/jobs') else self.stage_artifacts
        rows=super().pages(endpoint,field)
        if endpoint.endswith('/releases/17/assets'):
            for row in rows:
                if self.release['draft'] or getattr(self,'public_alias',False):row['browser_download_url']=self.release['html_url'].replace('/tag/','/download/')+'/'+row['name']
            if self.changed_id:rows[0]['id']+=10000
            if self.wrong_url:rows[0]['browser_download_url']='https://outside.invalid/file'
        return rows
    def download(self,endpoint,target,max_bytes,accept=None):
        if '/actions/artifacts/991/zip' in endpoint:
            target.write_bytes(self.transport);return
        super().download(endpoint,target,max_bytes,accept)
        if getattr(self,'swap_after_readback',False) and endpoint.endswith('/'+str(len(self.assets))):self.changed_id=True


def fixture(root):
    f=old.fixture();f['c']['publication_enabled']=True;api=Api(f)
    contract=root/'contract.json';contract.write_bytes(p.encoded(f['c']))
    output=root/'stage';checksum=p.stage(contract,ORIGINAL,output,api)
    api.assets={path.name:path.read_bytes() for path in output.iterdir()}
    api.transport=old.zipped(api.assets)
    api.release=dict(id=17,tag_name=p.TAG,target_commitish=f['c']['source_revision'],draft=True,prerelease=True,
                     created_at='2026-10-16T21:00:00Z',html_url='https://github.com/'+p.REPOSITORY+'/releases/tag/untagged-abcdef1234')
    api.tag=dict(ref='refs/tags/'+p.TAG,object=dict(type='commit',sha=f['c']['source_revision']))
    api.changed_id=False;api.swap_after_readback=False;api.wrong_url=False
    api.stage_run=dict(id=990,run_attempt=1,workflow_id=994,path=r.WORKFLOW,head_sha=ORIGINAL,head_branch=p.BRANCH,event='push',status='completed',conclusion='failure',repository=dict(full_name=p.REPOSITORY,id=1408146704),head_repository=dict(full_name=p.REPOSITORY,id=1408146704))
    api.stage_jobs=[]
    for name,job,conclusion in [('guards',995,'success'),('stage',996,'success'),('publish',997,'failure')]:
        api.stage_jobs.append(dict(id=job,name=name,run_id=990,run_attempt=1,head_sha=ORIGINAL,status='completed',conclusion=conclusion,started_at='2026-10-16T20:00:00Z',completed_at='2026-10-16T21:00:00Z',steps=[dict(name='Create source-exact draft, verify all uploaded bytes, publish and verify again' if name=='publish' else 'passed',status='completed',conclusion=conclusion)]))
    pins=dict(transport=dict(id=991,name='x4-bootstrap-publication-'+ORIGINAL,**p.record(api.transport)),review=dict(id=992,name='x4-bootstrap-staging-review-'+ORIGINAL,**p.record(b'review')))
    api.stage_artifacts=[dict(id=v['id'],name=v['name'],size_in_bytes=v['bytes'],digest='sha256:'+v['sha256'],expired=False,created_at='2026-10-16T20:59:00Z',workflow_run=dict(id=990,head_sha=ORIGINAL,head_branch=p.BRANCH,repository_id=1408146704,head_repository_id=1408146704)) for v in pins.values()]
    resume=dict(schema=1,enabled=True,mode=r.MODE,release={k:api.release[k] for k in ('id','tag_name','target_commitish','html_url','created_at')},stage=dict(publisher_revision=ORIGINAL,publisher_tree='c'*40,run=dict(id=990,attempt=1,workflow_id=994,guard_job_id=995,stage_job_id=996,publish_job_id=997,workflow_sha256=p.sha(b'workflow')),artifacts=pins),checksum_sha256=checksum,transport_contract_sha256=p.sha(contract.read_bytes()),assets={n:dict(id=i+1,**p.record(raw)) for i,(n,raw) in enumerate(sorted(api.assets.items()))})
    path=root/'resume.json';path.write_bytes(p.encoded(resume));api.calls.clear()
    return contract,path,api,resume


class ResumeTests(unittest.TestCase):
    def env(self):return patch.dict(os.environ,GITHUB_SHA=CURRENT,GITHUB_EVENT_NAME='push',GITHUB_REPOSITORY=p.REPOSITORY,GITHUB_REF='refs/heads/'+p.BRANCH)
    def run_resume(self,root,contract,path,api):
        with self.env():r.resume(contract,path,CURRENT,root/'restored',api)
    def assert_no_write(self,api):self.assertFalse(any(row[0] in ('PATCH','POST','COMMAND') for row in api.calls))
    def test_resume_only_patches_exact_id_after_draft_readback_and_public_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);contract,path,api,_=fixture(root);self.run_resume(root,contract,path,api)
            writes=[x for x in api.calls if x[0] in ('PATCH','POST','COMMAND')]
            self.assertEqual(writes,[('PATCH',r.PREFIX+'/releases/17',{'draft':False,'prerelease':True,'make_latest':'false'})])
            index=api.calls.index(writes[0]);self.assertEqual(sum(x[0]=='DOWNLOAD' for x in api.calls[:index]),len(api.assets))
            self.assertEqual(sum(x[0]=='PUBLIC' for x in api.calls[index:]),len(api.assets))
    def test_wrong_existing_draft_identity_or_asset_id_prevents_any_write(self):
        for field,value in [('id',18),('target_commitish','d'*40),('draft',False),('tag_name','other'),('prerelease',False),('html_url','https://outside.invalid/untagged-a')]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);contract,path,api,_=fixture(root);api.release[field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):self.run_resume(root,contract,path,api)
                self.assert_no_write(api)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);contract,path,api,_=fixture(root);api.changed_id=True
            with self.assertRaises(ValueError):self.run_resume(root,contract,path,api)
            self.assert_no_write(api)
    def test_wrong_stage_run_attempt_source_job_or_artifact_prevents_write(self):
        for target,key,value in [('run','run_attempt',2),('run','conclusion','success'),('run','head_sha','d'*40),('job','id',123),('artifact','digest','sha256:'+'0'*64),('artifact','created_at','2026-10-16T22:00:00Z')]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);contract,path,api,_=fixture(root)
                obj=api.stage_run if target=='run' else api.stage_jobs[1] if target=='job' else api.stage_artifacts[0];obj[key]=value
                with self.subTest(target=target,key=key),self.assertRaises(ValueError):self.run_resume(root,contract,path,api)
                self.assert_no_write(api)
    def test_corrupt_draft_readback_or_replaced_asset_during_readback_prevents_write(self):
        for field in ('corrupt_readback','swap_after_readback','wrong_url'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);contract,path,api,_=fixture(root);setattr(api,field,True)
                with self.subTest(field=field),self.assertRaises(ValueError):self.run_resume(root,contract,path,api)
                self.assert_no_write(api)
    def test_public_download_failure_is_not_success_after_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);contract,path,api,_=fixture(root);api.public_unavailable=True
            with self.assertRaises(ValueError):self.run_resume(root,contract,path,api)
            self.assertEqual(sum(x[0]=='PATCH' for x in api.calls),1)
    def test_draft_alias_is_rejected_after_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);contract,path,api,_=fixture(root);api.public_alias=True
            with self.assertRaisesRegex(ValueError,'URL'):self.run_resume(root,contract,path,api)
            self.assertEqual(sum(x[0]=='PATCH' for x in api.calls),1)

    def test_streamed_archive_rejects_wrong_hash_members_links_encryption_and_sizes(self):
        for case in ('zip_hash','content','omitted','extra','duplicate','symlink','directory','size','encrypted','compression'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);_,_,api,lock=fixture(root);members=api.assets.copy();name=next(iter(members));raw=None
                if case=='zip_hash':raw=api.transport+b'changed'
                elif case=='content':members[name]+=b'bad'
                elif case=='omitted':del members[name]
                elif case=='extra':members['extra']=b'bad'
                elif case=='size':lock['assets'][name]['bytes']+=1
                if raw is None:
                    out=io.BytesIO()
                    with zipfile.ZipFile(out,'w') as z:
                        for n,data in members.items():
                            info=zipfile.ZipInfo(n)
                            if n==name and case=='compression':info.compress_type=zipfile.ZIP_BZIP2
                            if n==name and case=='symlink':info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
                            if n==name and case=='directory':info.filename=n+'/'
                            z.writestr(info,data)
                        if case=='duplicate':z.writestr(name,members[name])
                    raw=out.getvalue()
                    if case=='encrypted':
                        b=bytearray(raw);offset=b.index(b'PK\x01\x02');b[offset+8]|=1;raw=bytes(b)
                    lock['stage']['artifacts']['transport'].update(p.record(raw))
                archive=root/'transport.zip';archive.write_bytes(raw)
                with self.subTest(case=case),self.assertRaises((ValueError,RuntimeError,zipfile.BadZipFile)):
                    r.restore_transport(archive,root/'restored',lock)
    def test_archive_original_name_and_symlinked_paths_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,api,lock=fixture(root);archive=root/'transport.zip';archive.write_bytes(api.transport)
            original=zipfile.ZipFile.infolist
            def ambiguous(obj):
                rows=original(obj);rows[0].orig_filename=rows[0].filename+'\0ignored';return rows
            with patch.object(zipfile.ZipFile,'infolist',ambiguous),self.assertRaises(ValueError):r.restore_transport(archive,root/'restored',lock)
            alias=root/'alias.zip';alias.symlink_to(archive)
            with self.assertRaises(ValueError):r.restore_transport(alias,root/'restored',lock)
            parent=root/'alias-parent';parent.symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError):r.restore_transport(archive,parent/'restored',lock)

    def test_transport_and_embedded_evidence_are_never_read_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,api,lock=fixture(root);archive=root/'transport.zip';archive.write_bytes(api.transport)
            with patch.object(Path,'read_bytes',side_effect=AssertionError('Whole-file read prohibited')):
                r.restore_transport(archive,root/'restored',lock)
            self.assertEqual(p.file_record(root/'restored'/p.REPRODUCIBILITY),p.record(api.assets[p.REPRODUCIBILITY]))

    def test_original_archive_mutation_after_extraction_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,api,lock=fixture(root);archive=root/'transport.zip';archive.write_bytes(api.transport)
            actual=p.file_record;calls=0
            def changed(path):
                nonlocal calls
                if path==archive:
                    calls+=1
                    if calls==2:return {'bytes':1,'sha256':'0'*64}
                return actual(path)
            with patch.object(p,'file_record',side_effect=changed),self.assertRaises(ValueError):r.restore_transport(archive,root/'restored',lock)
    def test_resume_workflow_excludes_new_stage_create_and_upload(self):
        text=(old.ROOT/r.WORKFLOW).read_text();resume=text.split('  resume:\n',1)[1]
        self.assertIn("needs.guards.outputs.resume_enabled == 'true'",resume)
        self.assertEqual(text.count("needs.guards.outputs.resume_enabled != 'true'"),2)
        self.assertNotIn('upload-artifact',resume);self.assertNotIn('publish_x4_bootstrap.py publish',resume)
        self.assertIn('scripts/resume_x4_bootstrap.py',resume)
    def test_committed_resume_contract_is_exact(self):
        path=old.ROOT/'release/x4-bootstrap-123/resume.json'
        r.validate_contract(p.decode(path.read_bytes()),p.decode((old.ROOT/'release/x4-bootstrap-123/contract.json').read_bytes()))


if __name__=='__main__':unittest.main()
