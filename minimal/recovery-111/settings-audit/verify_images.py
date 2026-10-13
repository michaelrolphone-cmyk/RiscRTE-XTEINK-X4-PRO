#!/usr/bin/env python3
"""Read .103/.111 images and verify retained settings/provisioning contracts."""
import argparse,hashlib,json,pathlib,sys
p=argparse.ArgumentParser()
for n in ('runtime','baseline','selected','output'):p.add_argument('--'+n,type=pathlib.Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.runtime/'scripts'))
from spiffs_image import read_image
sha=lambda b:hashlib.sha256(b).hexdigest()
reports={};stores={};images={}
for version,path in [('103',a.baseline),('111',a.selected)]:
 b=path.read_bytes();assert len(b)==0x1000000
 files=read_image(b[0x2f0000:0x800000],0x510000);co=json.loads(files['cohort.json']);assert co['version']=='0.1.'+version
 fw=b[0x10000:0x10000+co['firmware_size']];assert sha(fw)==co['firmware_sha256']
 markers=['RTE_BOOT error=native-settings-backend','RTE_BOOT error=native-settings-admission','RTE_BOOT error=native-settings-hydration','/appdata/.native-settings','/.native-settings']
 assert all(s.encode() in fw for s in markers)
 reports[version]=dict(image_sha256=sha(b),cohort=co,compiled_markers=markers,appdata_sha256=sha(b[0x270000:0x2f0000]))
 stores[version]=files;images[version]=b
assert reports['111']['image_sha256']=='77fc8f87f1c4f825a35e17d65c7bf663b82bbab3be9f8f0f6973581529818b00'
assert reports['111']['cohort']['firmware_sha256']=='3242bc4ac994a9b60ab73588955b311508e221d092b8cbc270d9136c608ec026'
old=json.loads(stores['103']['boot.json']);new=json.loads(stores['111']['boot.json'])
assert old['installation']==new['installation']
assert new['installation']['settings_sd'] and new['installation']['volume_instance']==9
assert new['installation']['namespace_range']==dict(first=3000,count=128)
writers=[]
for name,identity,ns in [('settings','settings',1),('default','paper_clock',1),('battery','battery',1),('ble_scanner','ble_scanner',1),('contexts','contexts',1),('wifi_settings','wifi_settings',6)]:
 manifest=json.loads(stores['111'][name+'.json']);assert manifest['id']==identity
 row=next(x for x in new['app_capabilities'] if x['manifest']==name+'.json')
 previous=next(x for x in old['app_capabilities'] if x['manifest']==name+'.json')
 grants=lambda x:[g for g in x['grants'] if g['capability'].startswith('storage.key-value')]
 assert grants(previous)==grants(row)
 assert dict(api=1,capability='storage.key-value.atomic',instance_id=ns) in row['grants']
 if name in ('settings','default','wifi_settings'):assert dict(api=1,capability='storage.key-value.availability',instance_id=ns) in row['grants']
 writers.append(dict(manifest=name+'.json',app_id=identity,namespace=ns,version=manifest['version'],key_value_grants_unchanged=True,internal_elf_sha256=sha(stores['111'][name+'.elf']) if name+'.elf' in stores['111'] else None,image_source=row.get('image_source')))
assert stores['103']['settings.elf']==stores['111']['settings.elf']
assert images['103'][0x270000:0x2f0000]==images['111'][0x270000:0x2f0000]
result=dict(images=reports,writers=writers,installation_unchanged=True,settings_elf_unchanged=True,appdata_image_unchanged=True,compiled_markers_are_not_a_native_rebuild=True,hardware_tested=False)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print('Selected settings grants, provisioning, backend markers and preserved .103 settings payload PASS')
