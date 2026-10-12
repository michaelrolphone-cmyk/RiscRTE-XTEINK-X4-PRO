#!/usr/bin/env python3
"""Offline positive/negative checks for the complete .97-to-.98 OBD overlay."""
import argparse,copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_obd_098 as c
p=argparse.ArgumentParser()
for name in ('baseline','app','scene','driver','tools','runtime'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();base,old,sd,parts,previous=c.baseline(a.baseline)
app,scene,driver=map(c.read_tree,(a.app,a.scene,a.driver));revision='a'*40
new,new_sd=c.payload(old,sd,app,scene,driver,revision)
assert new['file_browser.elf']==old['file_browser.elf'] and new['file_browser.json']==old['file_browser.json']
assert new['default.elf']==old['default.elf'] and all(new_sd[n]==v for n,v in sd.items())
assert json.loads(new['boot.json'])['installation']==json.loads(old['boot.json'])['installation']
pack,decode,bank,parse=c.load_assembly_tools(a.tools,a.runtime)
image,packing=c.ordered_build(new,pack);again,other=c.ordered_build(dict(reversed(list(new.items()))),pack)
assert image==again and packing==other and packing['ordered_paths'][:2]==['boot.json','board.json']
assert len(packing['ordered_paths'])==106 and len(set(packing['ordered_paths']))==106
result=bytearray(previous);result[slice(*c.BOOTFS)]=image;result[slice(*c.BANK_STATE)]=bank(parts['firmware.bin'],image,True)
c.verify_image(bytes(result),previous,old,new,parts['firmware.bin'],decode,parse)
rejected=[]
def reject(name,call):
 try:call()
 except (ValueError,AssertionError,KeyError):rejected.append(name);return
 raise AssertionError('Accepted '+name)
for role,files,path in [('app',app,'obd_dashboard.elf'),('scene',scene,'driver.elf'),('serial',driver,'driver.elf')]:
 bad=dict(files);bad[path]+=b'x';args=[app,scene,driver];args[['app','scene','serial'].index(role)]=bad
 reject('changed-'+role+'-elf',lambda:c.payload(old,sd,*args,revision))
for role,files,path in [('app',app,'obd_dashboard.json'),('scene',scene,'manifest.json'),('serial',driver,'manifest.json')]:
 for key,value in [('version','99.0.0'),('type','invalid'),('file_name','other.elf'),('requires',[])]:
  bad=dict(files);manifest=json.loads(bad[path]);manifest[key]=value;bad[path]=c.encoded(manifest);args=[app,scene,driver];args[['app','scene','serial'].index(role)]=bad
  reject(role+'-metadata-'+key,lambda:c.payload(old,sd,*args,revision))
for offset in (0,0x10000,0x26ffff,0x270000,0x800000,0xff0000,0xff4000,0xffffff,c.BOOTFS[0],c.BANK_STATE[0]+15,c.BANK_STATE[0]+95,c.BANK_STATE[0]+96):
 bad=bytearray(result);bad[offset]^=1
 reject('flash-'+hex(offset),lambda:c.verify_image(bytes(bad),previous,old,new,parts['firmware.bin'],decode,parse))
for path in ('boot.json','cohort.json','default.elf','file_browser.elf','file_browser.json'):
 bad=dict(new);bad[path]+=b'x'
 reject('readback-'+path,lambda:c.verify_image(bytes(result),previous,old,bad,parts['firmware.bin'],decode,parse))
reject('truncated-image',lambda:c.verify_image(bytes(result[:-1]),previous,old,new,parts['firmware.bin'],decode,parse))
print(json.dumps(dict(passed=True,negative_probes=len(rejected),rejected=rejected,deterministic=True,existing_sd_files_preserved=len(sd),selected_sd_images=48,files_and_home_unchanged=True,general_installation_envelope_unchanged=True,empty_blocks=packing['empty_blocks'],hardware_tested=False),indent=2))
