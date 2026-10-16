#!/usr/bin/env python3
"""Synthetic guards for explicitly split producer/qualification provenance."""
import base64
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_x4_bootstrap_publication as old
p=old.p
r=p.recovery


def fixture():
    f=old.fixture(); c=f['c']; files=f['files']; evidence=f['evidence']
    qualifier='d'*40; tree='e'*40
    c['run'].update(event='pull_request', pull_request=45, head_branch='work/x4-bootstrap-0.1.123')
    f['run']['repository']['id']=f['run']['head_repository']['id']=1408146704
    f['run'].update(event='pull_request', conclusion='failure', head_branch=c['run']['head_branch'],
                    pull_requests=[{'number':45,'head':{'sha':c['source_revision'],'ref':c['run']['head_branch'],'repo':{'id':1408146704}},'base':{'repo':{'id':1408146704}}}])
    job=f['jobs'][0]; job.update(conclusion='failure',run_attempt=1)
    job['steps'] += [{'name':n,'status':'completed','conclusion':'success'} for n in
        ('Clone exact independent clean source roots','Download and audit the immutable .122 factory and matching complete SD')]
    for step in job['steps']:
        if step['name']=='Fresh .123 packages and native build with complete qualification': step['conclusion']='failure'
        if step['name']=='Native artifact and workspace checks': step['conclusion']='skipped'
    original_qualification=copy.deepcopy(c['artifacts']['qualification'])
    recovery_run=dict(id=111,attempt=1,workflow_id=112,job_id=113,event='push',head_branch=r.BRANCH,workflow_path=r.WORKFLOW,workflow_sha256=p.sha(b'recovery workflow'))
    c['qualification_recovery']=dict(schema=1,mode=r.MODE,source_revision=qualifier,source_tree=tree,run=recovery_run,
        custody_receipt_sha256='0'*64, archive_contract_sha256='0'*64,producer_qualification_artifact=original_qualification,
        admission_inputs_artifact=dict(id=124,name='x4-native-provision-123-admission-inputs-'+qualifier,**p.record(b'inputs')))
    q=p.decode(files['qualification.json']); lock=q['input_lock']
    grant = dict(capability='storage.key-value', api=1, instance_id=6)
    old_boot = dict(app_capabilities=[dict(manifest='default.json', grants=[]), dict(manifest='clock.json', grants=[grant])])
    boot = copy.deepcopy(old_boot); boot['app_capabilities'][0]['grants'].append(grant)
    files['store/boot.json'] = p.encoded(boot)
    baseline = p.decode(f['baseline']); baseline['files']['boot.json'] = p.record(p.encoded(old_boot))
    f['baseline'] = p.encoded(baseline); c['baseline_sha256'] = p.sha(f['baseline'])
    q['baseline_contract'] = baseline; lock['baseline_contract_sha256'] = c['baseline_sha256']
    feed = p.decode(files['feed/native-packages-v1.json'])
    feed['boot_profiles']['core']['profile']['files'] = [[name[6:], len(raw), p.sha(raw)]
        for name, raw in sorted(files.items()) if name.startswith('store/')]
    files['feed/native-packages-v1.json'] = p.encoded(feed)
    receipt = p.decode(files['feed/receipt.json'])
    receipt.update(feed_sha256=p.sha(files['feed/native-packages-v1.json']), feed_bytes=len(files['feed/native-packages-v1.json']))
    files['feed/receipt.json'] = p.encoded(receipt)
    lock['package_build']={'same_process_build':True,'sources':c['sources']}
    files['source-lock.json']=p.encoded(lock); q['input_lock_sha256']=p.sha(files['source-lock.json'])
    archive=dict(schema=1,qualification_enabled=True,repository=p.REPOSITORY,source_revision=c['source_revision'],source_tree=c['source_tree'],
        original_root='/__w/_temp/x4-provision-123-'+c['source_revision'],artifact=c['artifacts']['reproducibility'],
        run={k:c['run'][k] for k in ('id','attempt','job_id','workflow_id','event','pull_request','head_branch')} |
            dict(workflow=p.WORKFLOW,workflow_sha256=c['run']['workflow_sha256'],repository_id=1408146704,conclusion='failure'))
    files['archive-contract.json']=p.encoded(archive)
    files['original-build-closure.json']=p.encoded(q['build_closure'])
    files['original-package-build-receipt.json']=p.encoded(lock['package_build'])
    delta={'scripts/native_provision_requalify.py':dict(mode='100644',producer=None,qualifier=p.record(b'new qualifier'))}
    custody=dict(schema=1,mode=r.MODE,fresh_build=False,same_process_qualification=False,native_rebuilt=False,packages_rebuilt=False,hardware_tested=False,target_instructions_executed=False,
        producer_source=lock['sources']['product'],qualifier=dict(source=dict(revision=qualifier,tree=tree,submodules=[]),changed_files=delta),
        qualification_run=dict(repository=p.REPOSITORY,run_id=111,attempt=1,source=qualifier),archive_contract=archive,
        archive_contract_sha256=p.sha(files['archive-contract.json']),original_source_lock_sha256=p.sha(files['source-lock.json']),
        original_build_closure_sha256=p.sha(files['original-build-closure.json']),original_package_receipt_sha256=p.sha(files['original-package-build-receipt.json']),
        restored_files={'build/'+v['path']:{k:v[k] for k in ('bytes','sha256')} for v in lock['native_files'].values()})
    custody['restored_files'].update({path:p.record(files[name]) for path,name in r.ORIGINAL_RECEIPTS.items()})
    files['archive-recovery.json']=p.encoded(custody); q['qualification_recovery']=custody
    c['qualification_recovery'].update(custody_receipt_sha256=p.sha(files['archive-recovery.json']),archive_contract_sha256=p.sha(files['archive-contract.json']))
    candidate_digest, baseline_digest, control_digest = r.admission_digests(files, baseline, p.decode)
    for key in ('admission','admission_sanitized'):
        row=q[key]; row.update(mode='factory-bootstrap-self-admission',active_store_sha256=candidate_digest,candidate_store_sha256=candidate_digest,
            preserving_transition=dict(expected_rejection=True,prepared=True,cohort_validated=False,elf_count=0,hardware_calls=0,storage_calls=0,control_packaged=False,
                active_store_sha256=baseline_digest,candidate_store_sha256=candidate_digest,
                native_elf_sha256=lock['native_files']['firmware_elf']['sha256'],target_instructions_executed=False,
                reason='Existing paper_clock gains already-owned storage.key-value namespace 6 without migration authority.',
                runtime_guard='src/bootstrap/CohortRuntime.inc: used && !owned; !migrating',
                authority_only_control=dict(elf_count=43,prepared=True,cohort_validated=True,hardware_calls=0,storage_calls=0,
                                            active_store_sha256=baseline_digest,candidate_store_sha256=control_digest,
                                            native_elf_sha256=lock['native_files']['firmware_elf']['sha256'],target_instructions_executed=False)))
    q['preservation_software_model'].update(scope='byte-range-and-fault-order-only',preserving_transition_eligible=False,namespace_authority_tested=False)
    files['qualification.json']=p.encoded(q); old.refresh(f,feed=True)
    evidence.update({'candidate/'+name:files[name] for name in r.EXTRA_FILES})
    evidence['build/native-build-evidence/source-lock.json']=files['source-lock.json']
    f['archives'].update(candidate=old.zipped(files),qualification=old.zipped(evidence))
    for role in ('candidate','qualification'):
        c['artifacts'][role]=dict(id=120 if role=='candidate' else 121,name='x4-native-provision-123-'+role+'-'+qualifier,**p.record(f['archives'][role]))
    pins=[c['artifacts']['reproducibility'],original_qualification]
    f['artifacts']=[artifact(v,c['run'],c['source_revision']) for v in pins]
    f['recovery_run']={**f['run'],'id':111,'run_attempt':1,'workflow_id':112,'path':r.WORKFLOW,'head_sha':qualifier,'head_branch':r.BRANCH,'event':'push','conclusion':'success','pull_requests':[]}
    f['recovery_jobs']=[{**job,'id':113,'run_id':111,'head_sha':qualifier,'name':'requalify','conclusion':'success','steps':[dict(name=n,status='completed',conclusion='success') for n in r.STEPS]}]
    f['recovery_artifacts']=[artifact(v,recovery_run,qualifier) for v in (c['artifacts']['candidate'],c['artifacts']['qualification'],c['qualification_recovery']['admission_inputs_artifact'])]
    f['recovery_commit']={'sha':qualifier,'commit':{'tree':{'sha':tree}}}
    f['delta']=delta
    return f


def artifact(pin,run,source):
    return dict(id=pin['id'],name=pin['name'],size_in_bytes=pin['bytes'],digest='sha256:'+pin['sha256'],expired=False,created_at='2026-10-16T20:59:00Z',
        workflow_run=dict(id=run['id'],head_sha=source,head_branch=run['head_branch'],repository_id=1408146704,head_repository_id=1408146704))


class FakeGithub(old.FakeGithub):
    def json(self,endpoint,method='GET',body=None):
        if '/actions/runs/111/' in endpoint: return self.f['recovery_run']
        if '/commits/'+self.f['c']['qualification_recovery']['source_revision'] in endpoint: return self.f['recovery_commit']
        if '/contents/'+r.WORKFLOW+'?' in endpoint:
            return dict(type='file',encoding='base64',path=r.WORKFLOW,content=base64.b64encode(b'recovery workflow').decode())
        return super().json(endpoint,method,body)
    def pages(self,endpoint,field=None):
        if '/actions/runs/111/' in endpoint:
            return self.f['recovery_jobs'] if '/jobs' in endpoint else self.f['recovery_artifacts']
        return super().pages(endpoint,field)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.base=fixture()
    def setUp(self): self.f=copy.deepcopy(self.base)
    def test_valid_split_contract_candidate_and_official_runs(self):
        f=self.f;p.final_contract(f['c']);old.verify(f)
        p.verify_ci(f['c'],f['run'],f['jobs'],f['artifacts'],f['commit'],f['workflow'])
        with patch.object(r,'official_delta',return_value=f['delta']):
            metadata=p.official_inputs(FakeGithub(f),f['c']);r.verify_source_delta(f['files'],metadata,p.decode)
    def test_legacy_success_path_remains_strict(self):
        f=self.f; del f['c']['qualification_recovery']
        with self.assertRaises(ValueError):p.verify_ci(f['c'],f['run'],f['jobs'],f['artifacts'],f['commit'],f['workflow'])
    def test_original_additional_failure_or_wrong_attempt_rejects(self):
        for mutate in [lambda f:f['jobs'][0].update(run_attempt=2),lambda f:f['run'].update(conclusion='success'),
                       lambda f:f['jobs'][0]['steps'].append(dict(name='extra',status='completed',conclusion='failure'))]:
            f=copy.deepcopy(self.f);mutate(f)
            with self.assertRaises(ValueError):p.verify_ci(f['c'],f['run'],f['jobs'],f['artifacts'],f['commit'],f['workflow'])
    def test_extraction_only_or_skipped_recovery_step_rejects(self):
        for index in range(len(r.STEPS)):
            f=copy.deepcopy(self.f);f['recovery_jobs'][0]['steps'][index]['conclusion']='skipped'
            with self.assertRaises(ValueError),patch.object(r,'official_delta',return_value=f['delta']):p.official_inputs(FakeGithub(f),f['c'])
    def test_recovery_run_source_attempt_and_artifact_identity_reject(self):
        for group,key,value in [('recovery_run','head_sha','a'*40),('recovery_run','run_attempt',2),('recovery_run','event','workflow_dispatch'),('recovery_run','conclusion','failure')]:
            f=copy.deepcopy(self.f);f[group][key]=value
            with self.assertRaises(ValueError),patch.object(r,'official_delta',return_value=f['delta']):p.official_inputs(FakeGithub(f),f['c'])
        self.f['recovery_artifacts'][0]['workflow_run']['id']=11
        with self.assertRaises(ValueError),patch.object(r,'official_delta',return_value={}):p.official_inputs(FakeGithub(self.f),self.f['c'])
    def mutate_custody(self,mutate):
        f=self.f;v=p.decode(f['files']['archive-recovery.json']);mutate(v)
        f['files']['archive-recovery.json']=p.encoded(v)
        q=p.decode(f['files']['qualification.json']);q['qualification_recovery']=v;f['files']['qualification.json']=p.encoded(q)
        f['c']['qualification_recovery']['custody_receipt_sha256']=p.sha(f['files']['archive-recovery.json'])
        old.refresh(f);f['evidence']['candidate/archive-recovery.json']=f['files']['archive-recovery.json']
    def test_custody_cannot_claim_fresh_rebuilt_or_hardware(self):
        for key in ('fresh_build','same_process_qualification','native_rebuilt','packages_rebuilt','hardware_tested','target_instructions_executed'):
            self.f=copy.deepcopy(self.base);self.mutate_custody(lambda v:v.update({key:True}))
            with self.assertRaises(ValueError):old.verify(self.f)
    def test_restored_native_or_original_receipt_mutation_rejects(self):
        self.mutate_custody(lambda v:v['restored_files']['build/firmware.bin'].update(sha256='f'*64))
        with self.assertRaises(ValueError):old.verify(self.f)
        self.f=copy.deepcopy(self.base);self.f['files']['original-build-closure.json']+=b' '
        with self.assertRaises(ValueError):old.verify(self.f)
    def test_restored_original_receipt_entries_cannot_be_omitted_or_substituted(self):
        for path in r.ORIGINAL_RECEIPTS:
            for omit in (False,True):
                self.f=copy.deepcopy(self.base)
                def mutate(v):
                    if omit:del v['restored_files'][path]
                    else:v['restored_files'][path]=p.record(b'substituted receipt')
                self.mutate_custody(mutate)
                with self.subTest(path=path,omit=omit),self.assertRaises(ValueError):old.verify(self.f)

    def test_archive_contract_must_bind_original_producer(self):
        f=self.f;v=p.decode(f['files']['archive-contract.json']);v['run']['id']=999
        f['files']['archive-contract.json']=p.encoded(v)
        f['evidence']['candidate/archive-contract.json']=f['files']['archive-contract.json']
        f['c']['qualification_recovery']['archive_contract_sha256']=p.sha(f['files']['archive-contract.json'])
        self.mutate_custody(lambda x:x.update(archive_contract=v,archive_contract_sha256=p.sha(f['files']['archive-contract.json'])))
        with self.assertRaises(ValueError):old.verify(f)
    def test_qualifier_delta_disallows_native_changes(self):
        self.mutate_custody(lambda v:v['qualifier']['changed_files'].update({'minimal/src/main.cpp':dict(mode='100644',producer=None,qualifier=p.record(b'bad'))}))
        with self.assertRaises(ValueError):old.verify(self.f)
    def test_official_delta_must_equal_reported_source_delta(self):
        with self.assertRaises(ValueError):r.verify_source_delta(self.f['files'],{'qualification-source-delta.json':b'{}'},p.decode)
    def test_self_admission_negative_control_and_model_are_required(self):
        for key,value in [('expected_rejection',False),('cohort_validated',True),('elf_count',43),('hardware_calls',1),('control_packaged',True),('reason','unrelated')]:
            f=copy.deepcopy(self.base);q=p.decode(f['files']['qualification.json']);q['admission']['preserving_transition'][key]=value
            f['files']['qualification.json']=p.encoded(q);old.refresh(f)
            with self.assertRaises(ValueError):old.verify(f)
        f=copy.deepcopy(self.base);q=p.decode(f['files']['qualification.json']);q['preservation_software_model']['preserving_transition_eligible']=True
        f['files']['qualification.json']=p.encoded(q);old.refresh(f)
        with self.assertRaises(ValueError):old.verify(f)
    def test_canonical_inventory_digest_matches_helper_format(self):
        rows={'b':dict(bytes=2,sha256=p.sha(b'bc')), 'a':dict(bytes=1,sha256=p.sha(b'a'))}
        raw=b'[{"path":"a","sha256":"'+p.sha(b'a').encode()+b'","size_bytes":1},{"path":"b","sha256":"'+p.sha(b'bc').encode()+b'","size_bytes":2}]'
        self.assertEqual(r.inventory_digest(rows),p.sha(raw))

    def test_coherently_forged_admission_digests_reject(self):
        for target in ('candidate','baseline','control'):
            f=copy.deepcopy(self.base);q=p.decode(f['files']['qualification.json'])
            for key in ('admission','admission_sanitized'):
                row=q[key];negative=row['preserving_transition'];control=negative['authority_only_control']
                if target=='candidate':
                    row['active_store_sha256']=row['candidate_store_sha256']=negative['candidate_store_sha256']='a'*64
                elif target=='baseline':
                    negative['active_store_sha256']=control['active_store_sha256']='b'*64
                else:
                    control['candidate_store_sha256']='c'*64
            f['files']['qualification.json']=p.encoded(q);old.refresh(f)
            with self.subTest(target=target),self.assertRaises(ValueError):old.verify(f)

    def test_negative_controls_bind_exact_native_elf_and_no_execution(self):
        for nested in (False,True):
            for field,value in (('native_elf_sha256','e'*64),('target_instructions_executed',True)):
                f=copy.deepcopy(self.base);q=p.decode(f['files']['qualification.json'])
                for key in ('admission','admission_sanitized'):
                    row=q[key]['preserving_transition']
                    if nested:row=row['authority_only_control']
                    row[field]=value
                f['files']['qualification.json']=p.encoded(q);old.refresh(f)
                with self.subTest(nested=nested,field=field),self.assertRaises(ValueError):old.verify(f)

    def test_official_source_delta_validates_tree_blobs_and_allowed_paths(self):
        c=self.f['c']; name='scripts/native_provision_requalify.py'; raw=b'new qualifier'
        blob=hashlib.sha1(('blob %d\0' % len(raw)).encode()+raw).hexdigest()
        class Api:
            def __init__(self):self.truncated=False;self.path=name;self.blob=blob;self.mode='100644'
            def json(self,url):
                tree=url.split('/git/trees/')[1].split('?')[0]
                return dict(sha=tree,truncated=self.truncated,tree=[] if tree==c['source_tree'] else
                    [dict(path=self.path,type='blob',mode=self.mode,sha=self.blob)])
        api=Api()
        fetch=lambda api,revision,path:raw
        self.assertEqual(r.official_delta(api,c,fetch),self.f['delta'])
        for key,value in [('truncated',True),('path','minimal/main.cpp'),('blob','0'*40),('mode','120000')]:
            api=Api();setattr(api,key,value)
            with self.assertRaises(ValueError):r.official_delta(api,c,fetch)

    def test_full_stage_keeps_original_source_archive_and_separate_receipts(self):
        f=self.f
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'official_delta',return_value=f['delta']):
            root=Path(temp);contract=root/'contract.json';contract.write_bytes(p.encoded(f['c']))
            digest=p.stage(contract,old.PUBLISHER,root/'output',FakeGithub(f))
            c,files=p.verify_output(root/'output',digest,old.PUBLISHER)
            release=p.decode(files['release.json']);self.assertEqual(release['compiled_product_revision'],f['c']['source_revision'])
            self.assertEqual(release['qualification_recovery'],f['c']['qualification_recovery'])
            self.assertEqual(files[p.REPRODUCIBILITY].read_bytes(),f['archives']['reproducibility'])
            self.assertIn(b'original preserving-transition qualification failed',files['RELEASE-NOTES.txt'])


if __name__=='__main__':unittest.main()
