#!/usr/bin/env python3
"""Authority and byte-preservation checks for the .102 composition boundary."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compose_evening_102 import payload, checked_files, CHANGED, SD_CHANGED
from compose_files_092 import encoded, sha

class EveningCompositionTest(unittest.TestCase):
    def setUp(self):
        self.old = {
            'waterfall.json': encoded({'id':'waterfall','version':'0.3.2','requires':[{'capability':'radio.iq','api':1}]}),
            'default.json': encoded({'id':'clock','version':'0.4.13','requires':[]}),
            'alarm/manifest.json': encoded({'id':'alarm-service','version':'0.4.8','requires':[]}),
            'default.elf': b'old home', 'alarm/driver.elf': b'old alarm',
            'boot.json': encoded({'drivers':[{'manifest':'alarm/manifest.json', 'image_source':{
                'internal_fallback':True,'volume_instance':9,'path':'Drivers/alarm-service/image-old.elf'},
                'key_value':[{'key':'alarm_utc_cfg','access':'read','namespace':3}]}],
                'installation':{'reserved_apps':[]}}),
            'cohort.json': encoded({'version':'0.1.101','runtime_version':'0.2.28','source_revision':'old'}),
            'file_browser.elf': b'preserved Files', 'settings.elf': b'preserved Settings'}
        self.sd = {'Drivers/alarm-service/image-old.elf':b'old alarm',
            'Apps/waterfall/waterfall.elf':b'old RF', 'Apps/waterfall/manifest.json':self.old['waterfall.json'],
            'Apps/ebook-reader/ebook_reader.elf':b'preserved Reader','Books/user.epub':b'user book'}
        self.rf = {'waterfall.elf':b'new RF','waterfall.json':encoded(dict(json.loads(self.old['waterfall.json']),version='0.3.3'))}
        self.rtc = {'x4/store/default.elf':b'new home','x4/store/alarm/driver.elf':b'new alarm'}
        for n,v in [('default.json','0.4.14'),('alarm/manifest.json','0.4.10')]:
            self.rtc['x4/store/'+n]=encoded(dict(json.loads(self.old[n]),version=v))

    def test_exact_scope_and_old_sd_preserved(self):
        old,sd=copy.deepcopy(self.old),copy.deepcopy(self.sd)
        new,after,row=payload(old,sd,self.rf,self.rtc,'a'*40)
        self.assertEqual({n for n in old if old[n]!=new[n]},CHANGED)
        self.assertEqual({n for n in sd if sd[n]!=after[n]},SD_CHANGED)
        self.assertEqual(set(after)-set(sd),{row['path']})
        self.assertEqual(after[row['path']],new['alarm/driver.elf'])
        self.assertEqual(after[row['previous_path']],b'old alarm')
        self.assertEqual(json.loads(new['cohort.json'])['source_revision'],'a'*40)
        self.assertEqual((old,sd),(self.old,self.sd))

    def test_grant_addition_rejected(self):
        self.rf['waterfall.json']=encoded({'id':'waterfall','version':'0.3.3','requires':[]})
        with self.assertRaisesRegex(ValueError,'Manifest authority'):
            payload(self.old,self.sd,self.rf,self.rtc,'a'*40)

    def test_sd_alarm_mismatch_rejected(self):
        self.sd['Drivers/alarm-service/image-old.elf']=b'stale'
        with self.assertRaisesRegex(ValueError,'Stale baseline'):
            payload(self.old,self.sd,self.rf,self.rtc,'a'*40)

    def test_experimental_binding_rejected(self):
        boot=json.loads(self.old['boot.json']);boot['installation']['shared_settings']=[]
        self.old['boot.json']=encoded(boot)
        with self.assertRaisesRegex(ValueError,'Unqualified shared settings'):
            payload(self.old,self.sd,self.rf,self.rtc,'a'*40)

    def test_immutable_collision_rejected(self):
        self.sd['Drivers/alarm-service/image-'+sha(b'new alarm')+'.elf']=b'new alarm'
        with self.assertRaisesRegex(ValueError,'Immutable alarm image collision'):
            payload(self.old,self.sd,self.rf,self.rtc,'a'*40)

    def test_wrong_volume_rejected(self):
        boot=json.loads(self.old['boot.json']);boot['drivers'][0]['image_source']['volume_instance']=10
        self.old['boot.json']=encoded(boot)
        with self.assertRaisesRegex(ValueError,'fallback authority'):
            payload(self.old,self.sd,self.rf,self.rtc,'a'*40)

    def test_wrong_baseline_version_rejected(self):
        self.old['cohort.json']=encoded({'version':'0.1.100','runtime_version':'0.2.28'})
        with self.assertRaisesRegex(ValueError,'predecessor cohort'):
            payload(self.old,self.sd,self.rf,self.rtc,'a'*40)

    def test_artifact_hash_and_length_required(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'a').write_bytes(b'good')
            pin={'a':{'sha256':sha(b'good'),'bytes':4}}
            self.assertEqual(checked_files(root,pin),{'a':b'good'})
            (root/'a').write_bytes(b'evil')
            with self.assertRaisesRegex(ValueError,'custody mismatch'):checked_files(root,pin)
            (root/'a').write_bytes(b'good');pin['a']['bytes']=5
            with self.assertRaisesRegex(ValueError,'custody mismatch'):checked_files(root,pin)

if __name__=='__main__':unittest.main()
