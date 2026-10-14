#!/usr/bin/env python3
"""Compose T057 from exact delivered .114. No native compile or device access."""
from pathlib import Path
import argparse,json,hashlib,sys,zipfile,subprocess
p=argparse.ArgumentParser()
for n in ('baseline','previous-sd','original-obd','test','scene','runtime','watch','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sys.path[:0]=[str(a.runtime/'scripts'),str(a.watch/'scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=a.baseline.read_bytes();assert sha(raw)=='8352746f381525cf23360e6f7d4986e7d4a4be8bb13b26d155e6da32658fd545'
size=0x510000;before=read_image(raw[0x2f0000:0x800000],size);store=dict(before)
# Prove the packer before changing contents.
oldpacked,_=current_bootfs.build(before,size=size);assert oldpacked==raw[0x2f0000:0x800000]
app=(a.test/'obd_test.elf').read_bytes();appmeta=(a.test/'obd_test.json').read_bytes();scene=(a.scene/'driver.elf').read_bytes()
assert sha(app)==json.loads((a.test/'build.json').read_text())['sha256']
assert sha(scene)==json.loads((a.scene/'build.json').read_text())['sha256']
assert json.loads(appmeta)['requires']==json.loads(before['obd_test.json'])['requires']
store['obd_test.json']=appmeta;store['ui-scene/driver.elf']=scene;store['ui-scene/manifest.json']=(a.scene/'manifest.json').read_bytes()
boot=json.loads(before['boot.json']);previous_boot=json.loads(before['boot.json'])
rows=[x for x in boot['drivers'] if x['manifest']=='ui-scene/manifest.json'];assert len(rows)==1
oldpath=rows[0]['image_source']['path'];newpath='Drivers/scene-host/image-'+sha(scene)+'.elf';rows[0]['image_source']['path']=newpath
store['boot.json']=json.dumps(boot,separators=(',',':')).encode()
# Only the provider's source path changes; all grants/app registrations remain exact.
rows[0]['image_source']['path']=oldpath;assert boot==previous_boot
source=subprocess.check_output(['git','-C',str(Path(__file__).resolve().parents[2]),'rev-parse','HEAD'],text=True).strip()
cohort=json.loads(before['cohort.json']);cohort.update(version='0.1.115',source_revision=source);store['cohort.json']=(json.dumps(cohort,indent=2)+'\n').encode()
changed=sorted(n for n in store if store[n]!=before[n]);assert changed==['boot.json','cohort.json','obd_test.json','ui-scene/driver.elf','ui-scene/manifest.json']
image,packing=current_bootfs.build(store,size=size);repeat,_=current_bootfs.build(store,size=size);assert image==repeat and read_image(image,size)==store
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
state=initial_bank_state(fw,image,True);parse_record(state[:96],True)
full=bytearray(raw);full[0x2f0000:0x800000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x800000:0xff2000]==raw[0x800000:0xff2000] and full[0xff3000:]==raw[0xff3000:]
out=a.output;out.mkdir(parents=True,exist_ok=True);name='X4-0.1.115-T057-OBD-Test-factory-erases-data-0x0.bin';(out/name).write_bytes(full)
for n,b in store.items():f=out/'store'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
with zipfile.ZipFile(a.previous_sd) as z:sd={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
for n in ['manifest.json','obd_dashboard.elf']:sd['Apps/obd-dashboard/'+n]=(a.original_obd/n).read_bytes()
assert json.loads(sd['Apps/obd-dashboard/manifest.json'])['version']=='0.2.2'
sd['Apps/obd-test/manifest.json']=appmeta;sd['Apps/obd-test/obd_test.elf']=app;sd[newpath]=scene
sdname='X4-0.1.115-Cumulative-Changed-SD-Keep-Existing.zip'
with zipfile.ZipFile(out/sdname,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in sorted(sd.items()):
  item=zipfile.ZipInfo(n,(2026,10,14,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;z.writestr(item,b)
proof={'version':'0.1.115','file':name,'image_sha256':sha(full),'baseline_sha256':sha(raw),'sd_file':sdname,'sd_sha256':sha((out/sdname).read_bytes()),'source_revision':source,'changed_store_files':changed,'native_unchanged':True,'app_grants_unchanged':True,'home_unchanged':store['default.elf']==before['default.elf'],'working_obd_preserved':True,'baseline_store_reproduced':True,'packing_repeated_identically':True,'hardware_tested':False,'packing':packing,'inventory':{n:sha(b) for n,b in store.items()},'sd_inventory':{n:sha(b) for n,b in sd.items()}}
(out/'assembly-report.json').write_text(json.dumps(proof,indent=2)+'\n');print(name,proof['image_sha256'])
