#!/usr/bin/env python3
"""Source-bound deployed ELF/manifest lifecycle correction and negative checks."""
import argparse,copy,io,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_sd_lifecycle_096 as c
import sd_resident_lifecycle as lifecycle
from elftools.elf.elffile import ELFFile
p=argparse.ArgumentParser()
for name in ('baseline','sd','tools','runtime'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();base,old,sd,parts,full=c.baseline(a.baseline,a.sd)
rejected=[]
def reject(name,fn):
 try:fn()
 except (ValueError,AssertionError,KeyError):rejected.append(name);return
 raise AssertionError('Accepted '+name)
reject('delivered-resident-metadata-omission',lambda:lifecycle.validate(old,sd))
new,new_sd,rows=c.payload(old,sd,'a'*40)
assert len(rows)==13 and len({r['id'] for r in rows})==13
assert len([p for p in old if old[p]==new[p]])==89
assert len([p for p in sd if sd[p]==new_sd[p]])==68
assert all(sd[p]==new_sd[p] for p in sd if p.endswith('.elf'))
assert old['boot.json']==new['boot.json'] and old['default.elf']==new['default.elf']
for row in rows:
 oldm=json.loads(old[row['manifest']]);newm=json.loads(new[row['manifest']])
 assert dict(oldm,runtime_lifecycle='foreground')==newm
 for mode in (None,'legacy','host','unknown'):
  bad,badsd=dict(new),dict(new_sd);m=dict(newm)
  if mode is None:del m['runtime_lifecycle']
  else:m['runtime_lifecycle']=mode
  bad[row['manifest']]=badsd[row['sd_manifest']]=c.encoded(m)
  reject(row['id']+'-wrong-mode-'+str(mode),lambda:lifecycle.validate(bad,badsd))
 badsd=dict(new_sd);badsd[row['sd_manifest']]=sd[row['sd_manifest']]
 reject(row['id']+'-mismatched-mirror',lambda:lifecycle.validate(new,badsd))
 blob=bytearray(new_sd[row['image']]);elf=ELFFile(io.BytesIO(blob));sym=elf.get_section_by_name('.symtab').get_symbol_by_name('risc_resident_app_descriptor_v1')[0]
 sec=elf.get_section(sym['st_shndx']);off=sec['sh_offset']+sym['st_value']-sec['sh_addr'];struct.pack_into('<I',blob,off+8,1)
 badsd=dict(new_sd);badsd[row['image']]=bytes(blob)
 reject(row['id']+'-wrong-elf-role',lambda:lifecycle.validate(new,badsd))
for field,value in (('version','9.9.9'),('requires',[]),('file_name','another.elf')):
 bad,badsd=dict(new),dict(new_sd);row=rows[0];m=json.loads(bad[row['manifest']]);m[field]=value
 bad[row['manifest']]=badsd[row['sd_manifest']]=c.encoded(m)
 reject('changed-authority-'+field,lambda:c.verify_payload(old,bad,sd,badsd,rows,'a'*40))
for path in ('Apps/gameboy/manifest.json','Apps/model_viewer/manifest.json','Apps/hollow_trail/manifest.json'):
 assert sd[path]==new_sd[path]
 badsd=dict(new_sd);m=json.loads(badsd[path]);m['runtime_lifecycle']='foreground';badsd[path]=c.encoded(m)
 reject('converted-legacy-'+path,lambda:c.verify_payload(old,new,sd,badsd,rows,'a'*40))
reject('repeat-repair',lambda:lifecycle.repair(new,new_sd))
for path in ('boot.json','default.elf','file_browser.elf'):
 bad=dict(new);bad[path]+=b'x';reject('unexpected-internal-'+path,lambda:c.verify_payload(old,bad,sd,new_sd,rows,'a'*40))
build,read_image,initial,parse=c.load_assembly_tools(a.tools,a.runtime)
image,packing=c.ordered_build(new,build);same,same_record=c.ordered_build(dict(reversed(list(new.items()))),build)
assert same==image and same_record==packing and packing['empty_blocks']>=2
result=bytearray(full);result[slice(*c.BOOTFS)]=image;result[slice(*c.BANK_STATE)]=initial(parts['firmware.bin'],image,True)
c.verify_image(bytes(result),full,old,new,read_image,parse,parts['firmware.bin'])
for off in (0,0x10000,0x26ffff,0x270000,0x800000,0xff0000,0xff4000,0xffffff,c.BOOTFS[0],c.BANK_STATE[0]+15,c.BANK_STATE[0]+96):
 bad=bytearray(result);bad[off]^=1
 reject('image-mutation-'+hex(off),lambda:c.verify_image(bytes(bad),full,old,new,read_image,parse,parts['firmware.bin']))
print(json.dumps(dict(passed=True,negative_probes=len(rejected),rejected=rejected,corrected_foreground_apps=13,
 preserved_legacy_apps=3,all_46_selected_ELFs_byte_identical=True,boot_authority_unchanged=True,
 deterministic_packing=True,empty_blocks=packing['empty_blocks'],occupied_blocks=packing['occupied_blocks'],
 hardware_tested=False),indent=2))
