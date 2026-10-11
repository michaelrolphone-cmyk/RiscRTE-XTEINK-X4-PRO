#!/usr/bin/env python3
"""Synthetic offline composition gate regressions; never opens a device/card."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/compose_shared_settings_090.py'
spec = importlib.util.spec_from_file_location('compose', SCRIPT)
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

class Composition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.base = self.root / 'base'; self.sd = self.root / 'sd'
        self.base.mkdir(); self.sd.mkdir(); (self.sd / 'existing.txt').write_text('synthetic app file')
        self.system = 'a'*40; self.runtime = 'b'*40; self.utilities = 'c'*40; self.modules = {}
        grants = [dict(capability='test.'+str(i), api=1, instance_id=i) for i in range(15)]
        grants.append(dict(capability='storage.app-data.export', api=1, instance_id=0))
        apps = [dict(manifest='file_browser.json', grants=grants)] + [dict(manifest='a'+str(i)+'.json', grants=[]) for i in range(25)]
        apps[0]['app_data_export'] = dict(label='Saved files', files=[dict(owner='timecard', namespace=1,
            name='timecard.json', path='/timecard/timecard.json', access='read-write')])
        apps[1] = dict(manifest='contexts.json',grants=[],image_source=dict(volume_instance=9,path='Apps/contexts/contexts.elf'))
        drivers = [dict(manifest='installed-apps/manifest.json', image_source=dict(volume_instance=9, internal_fallback=True, path='Drivers/old.elf'))] + [dict(manifest='d'+str(i)+'.json') for i in range(31)]
        self.boot = dict(app_capabilities=apps, drivers=drivers, installation=dict(settings_sd=True, volume_instance=9, namespace_range=dict(first=3000,count=128)))
        self.write(self.base/'boot.json', self.boot); self.write(self.base/'cohort.json', dict(version='0.1.89'))
        for name, version in c.VERSIONS.items():
            folder = self.root / name; folder.mkdir(); self.modules[name] = folder
            m = 'manifest.json' if name == 'installed-apps' else name+'.json'
            e = 'driver.elf' if name == 'installed-apps' else name+'.elf'
            target = self.base / ('installed-apps' if name == 'installed-apps' else ''); target.mkdir(exist_ok=True)
            needs = [dict(capability=x['capability'], api=x['api']) for x in grants] if name == 'file_browser' else []
            manifest = dict(id=name,version='0.0.1',file_name=e,requires=needs)
            self.write(target/m, manifest)
            if name == 'contexts':
                old=self.sd/'Apps/contexts';old.mkdir(parents=True);self.write(old/'manifest.json',manifest);(old/e).write_bytes(b'old synthetic ELF')
            else:(target/e).write_bytes(b'old synthetic ELF')
            manifest['version'] = version
            if name == 'file_browser':
                manifest['requires'] = [x for x in needs if x['capability'] != 'storage.app-data.export'] + [dict(capability='bluetooth.hci',api=1)]
            self.write(folder/m, manifest); (folder/e).write_bytes(('new synthetic '+name).encode())
            receipt = dict(sha256=c.sha(folder/e),repository_commit=self.system,working_tree_dirty=False)
            if name == 'installed-apps':
                receipt.update(repositories={'system':dict(head=self.system,dirty=False),'runtime':dict(head=self.runtime,dirty=False)},shared_settings_sd=True,shared_settings_root='/RTECFG')
            if name in ('default','springboard'):
                receipt['installed_catalog'] = dict(idle_settings_maintenance='settings_pending-v1',volume_instance=9)
            if name == 'default':
                receipt['installed_catalog']['alarm_reconcile_waits_for_shared_preferences']=True
                receipt.update(build_defines=['-DPORTABLE_DESK_LOCK_HOME','-DPORTABLE_DESK_POINTS_SNAPSHOT','-DPORTABLE_RESIDENT_SHELL_HOST'],sparse_start=True,desk_points=dict(retained_bytes=408))
            if name == 'file_browser':
                receipt.update(protected_settings=dict(root='/RTECFG',listing_open_mutation_copy=True),file_sharing=dict(app_data_export_required=False,protected_settings=dict(direct_recursive_and_peer=True),default_transport='ble-private-wifi',peer_files=True),required_grants=grants[:-1]+[dict(capability='bluetooth.hci',api=1,instance_id=16)])
            if name == 'wifi_settings':receipt['build_defines']=['-DPORTABLE_WIFI_PROFILES']
            if name == 'contexts':receipt.update(repositories={k:dict(head=v,dirty=False) for k,v in [('system',self.system),('runtime',self.runtime),('utilities',self.utilities)]},catalog_count=26,catalog_sha256=c.sha(c.ROOT/'minimal/contexts-090-catalog.json'),face_header=None,target_build=dict(sha256=c.sha(folder/e)))
            self.write(folder/c.RECORDS[name], receipt)
        c.BASE_RECEIPT = self.root/'baseline.json'; self.write(c.BASE_RECEIPT, dict(store=c.tree(self.base)))
        c.BASE_SD = self.root/'sd.json'; self.write(c.BASE_SD, dict(files=c.tree(self.sd)))

    def tearDown(self):self.tmp.cleanup()
    def write(self,p,x):p.write_text(json.dumps(x))
    def run_compose(self,namespaces=None):
        return c.compose(self.base,self.sd,self.modules,self.root/'out',self.system,self.runtime,[] if namespaces is None else namespaces,self.utilities)
    def mutate_receipt(self,name,fn):
        p=self.modules[name]/c.RECORDS[name];x=c.read(p);fn(x);self.write(p,x)
    def test_preserves_all_old_files_and_grant_bound(self):
        result=self.run_compose();self.assertEqual(result['preserved_sd_files'],3)
        self.assertEqual((self.root/'out/SD/existing.txt').read_bytes(),(self.sd/'existing.txt').read_bytes())
        b=c.read(self.root/'out/store/boot.json');self.assertNotIn('shared_settings',b['installation']);self.assertEqual(len(b['app_capabilities'][0]['grants']),16)
        self.assertNotIn('app_data_export',b['app_capabilities'][0])
        self.assertEqual(c.read(self.root/'out/store/cohort.json')['version'],'0.1.90')
    def test_contexts_preserves_old_sd_and_grants(self):
        self.run_compose();b=c.read(self.root/'out/store/boot.json');row=b['app_capabilities'][1]
        self.assertEqual(row['grants'],self.boot['app_capabilities'][1]['grants'])
        self.assertNotEqual(row['image_source']['path'],'Apps/contexts/contexts.elf')
        self.assertEqual((self.root/'out/SD/Apps/contexts/contexts.elf').read_bytes(),b'old synthetic ELF')
        self.assertEqual(c.read(self.root/'out/SD'/Path(row['image_source']['path']).parent/'manifest.json')['version'],'0.4.2')
        self.assertFalse((self.root/'out/store/contexts.elf').exists())
    def test_changed_baseline_rejected(self):
        (self.base/'default.elf').write_bytes(b'missing or changed baseline')
        with self.assertRaisesRegex(ValueError,'complete delivered'):self.run_compose()
    def test_changed_sd_rejected(self):
        (self.sd/'existing.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'complete delivered'):self.run_compose()
    def test_old_client_rejected(self):
        self.mutate_receipt('default',lambda x:x.pop('installed_catalog'))
        with self.assertRaisesRegex(ValueError,'maintenance'):self.run_compose()
    def test_unqualified_namespace_rejected(self):
        with self.assertRaisesRegex(ValueError,'disabled'):self.run_compose([1,6])
    def test_modified_binary_rejected(self):
        (self.modules['wifi_settings']/'wifi_settings.elf').write_bytes(b'unrecorded')
        with self.assertRaisesRegex(ValueError,'receipt'):self.run_compose()
    def test_missing_files_guard_rejected(self):
        self.mutate_receipt('file_browser',lambda x:x['protected_settings'].update(listing_open_mutation_copy=False))
        with self.assertRaisesRegex(ValueError,'guard'):self.run_compose()
    def test_seventeenth_grant_rejected(self):
        self.mutate_receipt('file_browser',lambda x:x['required_grants'].append(dict(capability='storage.app-data.export',api=1,instance_id=0)))
        with self.assertRaisesRegex(ValueError,'16-grant'):self.run_compose()
    def test_unique_zero_selector_resolves_to_existing_authority(self):
        self.mutate_receipt('file_browser',lambda x:x['required_grants'][3].update(instance_id=0))
        self.run_compose()
    def test_zero_selector_rejects_ambiguous_authority(self):
        rows=[dict(capability='storage.key-value',api=1,instance_id=n) for n in (1,6)]
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            c.resolved_grants([dict(capability='storage.key-value',api=1,instance_id=0)],rows)
    def test_explicit_selector_cannot_change_authority(self):
        self.mutate_receipt('file_browser',lambda x:x['required_grants'][3].update(instance_id=999))
        with self.assertRaisesRegex(ValueError,'16-grant'):self.run_compose()
    def test_stale_preferred_provider_is_retargeted_without_deleting_old_image(self):
        native=self.base/'wifi';native.mkdir();(native/'driver.elf').write_bytes(b'qualified private AP provider')
        self.write(native/'manifest.json',dict(file_name='driver.elf'))
        old=self.sd/'Drivers/wifi/image-old.elf';old.parent.mkdir(parents=True);old.write_bytes(b'old station-only provider')
        boot=c.read(self.base/'boot.json');boot['drivers'][1]=dict(manifest='wifi/manifest.json',image_source=dict(volume_instance=9,internal_fallback=True,path='Drivers/wifi/image-old.elf'))
        self.write(self.base/'boot.json',boot);self.write(c.BASE_RECEIPT,dict(store=c.tree(self.base)));self.write(c.BASE_SD,dict(files=c.tree(self.sd)))
        result=self.run_compose();selected=c.read(self.root/'out/store/boot.json')['drivers'][1]['image_source']['path']
        self.assertNotEqual(selected,'Drivers/wifi/image-old.elf')
        self.assertEqual((self.root/'out/SD'/selected).read_bytes(),(native/'driver.elf').read_bytes())
        self.assertEqual((self.root/'out/SD/Drivers/wifi/image-old.elf').read_bytes(),old.read_bytes())
        self.assertEqual(len(result['repaired_sd_provider_sources']),1)
    def test_wrong_catalog_runtime_rejected(self):
        self.mutate_receipt('installed-apps',lambda x:x['repositories']['runtime'].update(head='c'*40))
        with self.assertRaisesRegex(ValueError,'Runtime source'):self.run_compose()
    def test_cold_alarm_cannot_block_restore(self):
        self.mutate_receipt('default',lambda x:x['installed_catalog'].pop('alarm_reconcile_waits_for_shared_preferences'))
        with self.assertRaisesRegex(ValueError,'Cold alarm'):self.run_compose()
    def test_lock_profile_cannot_shrink(self):
        self.mutate_receipt('default',lambda x:x['desk_points'].update(retained_bytes=128))
        with self.assertRaisesRegex(ValueError,'retained'):self.run_compose()

if __name__ == '__main__':unittest.main()
