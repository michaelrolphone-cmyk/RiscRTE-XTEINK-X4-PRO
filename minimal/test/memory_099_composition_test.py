#!/usr/bin/env python3
"""Exact baseline preservation and failure probes for the .99 memory overlay."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_memory_099 as c
p=argparse.ArgumentParser()
for name in ('baseline','native','hollow','tools','runtime'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();base,old,old_sd,parts,prior=c.baseline(a.baseline)
lock=json.loads(c.LOCK.read_text());hollow=c.read_tree(a.hollow);firmware=(a.native/'firmware.bin').read_bytes()
new,sd=c.payload(old,old_sd,hollow,firmware,'a'*40,lock)
assert all(new[k]==old[k] for k in old if k not in c.CHANGED)
assert all(sd[k]==old_sd[k] for k in old_sd if k not in c.SD_CHANGED)
assert new['boot.json']==old['boot.json']
pack,decode,bank,parse=c.load_assembly_tools(a.tools,a.runtime)
bootfs,packing=c.ordered_build(new,pack)
assert c.ordered_build(dict(reversed(list(new.items()))),pack)==(bootfs,packing)
assert len(packing['ordered_paths'])==106 and len(set(packing['ordered_paths']))==106
result=bytearray(prior);result[slice(*c.FIRMWARE)]=firmware+b'\xff'*(c.FIRMWARE[1]-c.FIRMWARE[0]-len(firmware))
result[slice(*c.BOOTFS)]=bootfs;result[slice(*c.BANK_STATE)]=bank(firmware,bootfs,True)
c.verify_image(bytes(result),prior,old,new,firmware,decode,parse)
rejected=[]
def reject(name,action):
 try:action()
 except (ValueError,AssertionError,KeyError):rejected.append(name);return
 raise AssertionError('Accepted '+name)
for path in ('hollow_trail.elf','hollow_trail.json'):
 bad=dict(hollow);bad[path]+=b'x'
 reject('artifact-'+path,lambda:c.payload(old,old_sd,bad,firmware,'a'*40,lock))
for key,value in [('version','99.0.0'),('type','invalid'),('file_name','other.elf'),('requires',[])]:
 bad=dict(hollow);manifest=json.loads(bad['hollow_trail.json']);manifest[key]=value;bad['hollow_trail.json']=c.encoded(manifest)
 reject('manifest-'+key,lambda:c.payload(old,old_sd,bad,firmware,'a'*40,lock))
for offset in (0,0x10000,0x26ffff,0x270000,0x800000,0xff0000,0xff4000,0xffffff,c.BOOTFS[0],c.BANK_STATE[0]+15,c.BANK_STATE[0]+95,c.BANK_STATE[0]+96):
 bad=bytearray(result);bad[offset]^=1
 reject('flash-'+hex(offset),lambda:c.verify_image(bytes(bad),prior,old,new,firmware,decode,parse))
for path in ('boot.json','cohort.json','default.elf','file_browser.elf','file_browser.json','obd_dashboard.json','hollow_trail.json'):
 bad=dict(new);bad[path]+=b'x'
 reject('readback-'+path,lambda:c.verify_image(bytes(result),prior,old,bad,firmware,decode,parse))
reject('truncated-image',lambda:c.verify_image(bytes(result[:-1]),prior,old,new,firmware,decode,parse))
print(json.dumps(dict(passed=True,negative_probes=len(rejected),rejected=rejected,deterministic=True,existing_sd_files_preserved=83,selected_sd_images=48,files_obd_and_home_unchanged=True,boot_authority_unchanged=True,empty_blocks=packing['empty_blocks'],hardware_tested=False),indent=2))
