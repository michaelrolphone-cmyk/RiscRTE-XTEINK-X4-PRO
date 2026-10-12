#!/usr/bin/env python3
"""Exercise exact-store placement and negative final-image preservation checks."""
import argparse,copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_boot_order_095 as c
import boot_order_spiffs as order
p=argparse.ArgumentParser();
for name in ('baseline','sd','tools','runtime'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();receipt,old,sd,parts,previous=c.baseline(a.baseline,a.sd)
build,read_image,initial,parse=c.load_assembly_tools(a.tools,a.runtime)
new=c.changed_store(old,'a'*40);image,packing=order.build(new,build)
again,again_record=order.build(dict(reversed(list(new.items()))),build)
assert image==again and packing==again_record
assert len(packing['ordered_paths'])==103 and len(set(packing['ordered_paths']))==103
assert packing['ordered_paths'][:2]==['boot.json','board.json']
assert packing['ordered_paths'][35]=='cohort.json'
assert packing['ordered_paths'][61:64]==['default.elf','board/driver.elf','sd/driver.elf']
assert packing['empty_blocks']==232 and packing['occupied_blocks']==1064
assert read_image(image,len(image))==new
assert old['default.elf']==new['default.elf'] and old['file_browser.elf']==new['file_browser.elf']
firmware=parts['firmware.bin'];result=bytearray(previous)
result[slice(*c.BOOTFS)]=image;result[slice(*c.BANK_STATE)]=initial(firmware,image,True)
c.verify(bytes(result),previous,old,new,read_image,parse,firmware,'a'*40)
rejected=[]
def reject(name,call):
 try:call()
 except (ValueError,AssertionError,KeyError):rejected.append(name);return
 raise AssertionError('Accepted '+name)
for offset in (0,0x10000,0x26ffff,0x270000,0x800000,0xff0000,0xff4000,0xffffff):
 bad=bytearray(result);bad[offset]^=1
 reject('unrelated-flash-'+hex(offset),lambda:c.verify(bytes(bad),previous,old,new,read_image,parse,firmware,'a'*40))
for offset in (c.BOOTFS[0],c.BOOTFS[0]+256,c.BANK_STATE[0]+15,c.BANK_STATE[0]+95,c.BANK_STATE[0]+96):
 bad=bytearray(result);bad[offset]^=1
 reject('store-or-bank-'+hex(offset),lambda:c.verify(bytes(bad),previous,old,new,read_image,parse,firmware,'a'*40))
for name in ('boot.json','default.elf','file_browser.json','alarm/driver.elf'):
 bad=dict(new);bad[name]+=b'x'
 reject('unexpected-file-'+name,lambda:c.verify(bytes(result),previous,old,bad,read_image,parse,firmware,'a'*40))
bad=dict(new);identity=json.loads(bad['cohort.json']);identity['runtime_version']='bad';bad['cohort.json']=c.encoded(identity)
reject('cohort-native-change',lambda:c.verify(bytes(result),previous,old,bad,read_image,parse,firmware,'a'*40))
reject('wrong-revision',lambda:c.verify(bytes(result),previous,old,new,read_image,parse,firmware,'b'*40))
bad=dict(new);del bad['default.elf'];reject('absent-boot-path',lambda:order.ordered_paths(bad))
for name in ('../escape','/absolute','x'*32):
 bad=dict(new);bad[name]=b'x';reject('invalid-path-'+name,lambda:order.build(bad,build))
print(json.dumps(dict(passed=True,negative_probes=len(rejected),rejected=rejected,deterministic=True,
 same_103_paths=True,identical_file_contents=102,cohort_identity_only=True,empty_blocks=232,metadata_files=61,hardware_tested=False),indent=2))
