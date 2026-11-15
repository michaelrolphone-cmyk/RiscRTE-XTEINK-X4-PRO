#!/usr/bin/env python3
"""Offline .124 controls. Synthetic deltas are never target qualification."""
import argparse, copy, io, json, sys, unittest, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import native_paired_candidate as c
import native_paired_payloads as p
import native_paired_qualification as q
ARGS=None

def fixture():
    if ARGS.baseline:
        sources={'runtime':ARGS.runtime,'image_helper':ARGS.image_helper}
        return c.baseline_bytes(ARGS.baseline,json.loads(c.CONTRACT.read_bytes()),sources)[2]
    boot={'app_capabilities':[{'manifest':'default.json','grants':[
        *[{'capability':f'retained.{i}','api':1,'instance_id':i} for i in range(24)],
        {'capability':'storage.key-value','api':1,'instance_id':6}]}],
        'drivers':[{'manifest':'installed-apps/manifest.json','image_source':{'volume_instance':9,'internal_fallback':True,'path':'Drivers/installed-apps/old.elf'}}]}
    return {'boot.json':p.encoded(boot),'cohort.json':p.encoded({'version':'0.1.123'}),
        'installed-apps/driver.elf':b'old service','installed-apps/manifest.json':p.encoded({'id':'installed-apps','version':'0.15.0','requires':[]}),
        'default.elf':b'unchanged Home','default.json':b'{"version":"0.4.20"}', 'settings.elf':b'unchanged settings'}

def prepared():
    before=fixture(); service=json.loads(before['installed-apps/manifest.json']);service['version']='0.15.1'
    packages={'installed-apps/driver.elf':b'fixture new service', 'installed-apps/manifest.json':p.encoded(service)}
    after=p.compose(before,b'RISC_RUNTIME_VERSION:0.4.7\0fixture firmware',{'sources':{'product':{'revision':'a'*40}}},packages)
    return before,after

class Controls(unittest.TestCase):
    def test_exact_four_replacements(self):
        before,after=prepared();receipt=p.preservation_receipt(before,after)
        self.assertEqual(set(receipt['changed']),p.CHANGED)
        self.assertEqual(receipt['unchanged_count'],len(before)-4)
        self.assertEqual(before['default.elf'],after['default.elf'])
        self.assertEqual(before['default.json'],after['default.json'])
        self.assertFalse(receipt['hardware_tested'])
    def test_unrelated_change_rejected(self):
        before,after=prepared();after['settings.elf']=b'changed'
        with self.assertRaises(ValueError):p.preservation_receipt(before,after)
    def test_missing_path_rejected(self):
        before,after=prepared();after.pop('default.json')
        with self.assertRaises(ValueError):p.preservation_receipt(before,after)
    def test_new_authority_rejected(self):
        before,after=prepared();boot=json.loads(after['boot.json']);boot['app_capabilities'][0]['grants'].append({'capability':'surprise','api':1,'instance_id':8});after['boot.json']=p.encoded(boot)
        with self.assertRaises(ValueError):p.preservation_receipt(before,after)
    def test_wrong_runtime_rejected(self):
        before,after=prepared()
        with self.assertRaises(ValueError):p.compose(before,b'RISC_RUNTIME_VERSION:0.4.8\0',{'sources':{'product':{'revision':'a'*40}}},{k:after[k] for k in p.CHANGED-{'cohort.json','boot.json'}})
    def test_cohort_receipt_fail_closed(self):
        before,after=prepared(); digest=lambda files:p.sha(p.encoded({n:p.sha(v) for n,v in sorted(files.items())}))
        for fault in (None,'prepared','cohort_validated','elf_count','hardware_calls','storage_calls','active_store_sha256','candidate_store_sha256'):
            calls=[]
            def run(active,candidate,expected):
                calls.append(expected)
                row={'prepared':True,'cohort_validated':True,'elf_count':43,'hardware_calls':0,'storage_calls':0,'active_store_sha256':digest(active),'candidate_store_sha256':digest(candidate)}
                if fault:row[fault]=False if fault in ('prepared','cohort_validated') else 1
                return row
            if fault:
                with self.assertRaises(ValueError):q.factory_admission(run,before,after,43,digest)
            else:
                proof=q.factory_admission(run,before,after,43,digest)
                self.assertEqual(calls,[True,True]);self.assertFalse(proof['preserving_transition']['flash_method_qualified'])
    def test_namespace_mapping_frozen(self):
        text=(ROOT/'profiles/native-paired-124.cmake').read_text()
        for token in ('RISC_NATIVE_SERIAL_SD_INSTANCE=9','RISC_NATIVE_SERIAL_SD_PROVIDER=','x4pro-sd','X4_VERSION=0.1.124-paired-candidate'):self.assertIn(token,text)
        self.assertIn('native_provision_admission_fixture.inc',(ROOT/'scripts/native_paired_qualification.py').read_text())
    def test_no_archive_authority_shortcut(self):
        import inspect
        self.assertNotIn('archived_evidence',inspect.signature(c.qualify).parameters)
        with self.assertRaises((ValueError,AttributeError)):c.qualify(None,{})
    def test_full_sd_is_additive_and_deterministic(self):
        before,after=prepared();contract=json.loads(c.CONTRACT.read_bytes())
        if ARGS.sd_archive:
            files=c.released_sd(ARGS.sd_archive,contract,ARGS.runtime)
        else:
            files={name:b'fixture '+name.encode() for name in contract['sd']['files']}
        archive,complete,target,proof=p.complete_sd(files,after,contract)
        self.assertEqual(len(complete),78);self.assertEqual(proof['baseline_file_count'],77)
        self.assertEqual({k:complete[k] for k in files},files)
        self.assertEqual(len(proof['added_paths']),1)
        self.assertFalse(proof['unrelated_files_deleted'])
        self.assertEqual(p.complete_sd(files,after,contract)[0],archive)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:self.assertEqual({n:z.read(n) for n in z.namelist()},complete)
        self.assertEqual(target['sd']['elf_count'],50)
        if ARGS.baseline and ARGS.sd_archive: self.assertEqual(len(proof['external_consumers']),49)
    def test_missing_sd_file_rejected(self):
        before,after=prepared();contract=json.loads(c.CONTRACT.read_bytes());files={name:b'fixture' for name in contract['sd']['files']};files.pop(next(iter(files)))
        with self.assertRaises(ValueError):p.complete_sd(files,after,contract)
    def test_sd_wrong_volume_rejected(self):
        before,after=prepared();contract=json.loads(c.CONTRACT.read_bytes());files={name:b'fixture' for name in contract['sd']['files']};boot=json.loads(after['boot.json']);next(r for r in boot['drivers'] if r['manifest']=='installed-apps/manifest.json')['image_source']['volume_instance']=12;after['boot.json']=p.encoded(boot)
        with self.assertRaises(ValueError):p.complete_sd(files,after,contract)
    def test_baseline_contract(self):
        contract=json.loads(c.CONTRACT.read_bytes())
        self.assertEqual(contract['successor_version'],'0.1.124');self.assertEqual(len(contract['files']),107)
        self.assertEqual(contract['factory_sha256'],'85d197fb4ea6f1bdf2f02705b701c7e6667362a20cb856672c46b49fd51265b0')
        self.assertEqual(len(contract['sd']['files']),77)
    def test_release_gate_retained(self):
        cfg=p.config();self.assertFalse(cfg['publication_enabled']);self.assertTrue(cfg['installed_bootstrap_required_for_publication'])
        self.assertEqual(cfg['candidate_version'],'0.1.124')
        self.assertTrue(cfg['feed_base_url'].endswith('/test-native-paired-0.1.124/'))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path);parser.add_argument('--image-helper',type=Path);parser.add_argument('--baseline',type=Path);parser.add_argument('--sd-archive',type=Path)
    ARGS,extra=parser.parse_known_args()
    if ARGS.baseline and not (ARGS.runtime and ARGS.image_helper):parser.error('Exact baseline needs runtime and image helper')
    unittest.main(argv=[sys.argv[0],*extra])
