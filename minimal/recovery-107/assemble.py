#!/usr/bin/env python3
"""Compose Clock/Home 0.4.18 over the exact delivered X4 0.1.106 image.

No hardware access. Keep all unrelated logical files and flash ranges unchanged.
"""
import argparse,hashlib,importlib.util,json,struct,sys,tempfile
from pathlib import Path

def sha(data): return hashlib.sha256(data).hexdigest()
def require(ok,message):
 if not ok: raise ValueError(message)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('baseline','home','runtime','spiffsgen','output'):
  p.add_argument('--'+n,required=True,type=Path)
 p.add_argument('--system-commit',required=True)
 a=p.parse_args();sys.path.insert(0,str(a.runtime/'scripts'))
 from spiffs_image import read_image
 from paired_bank_images import initial_bank_state,parse_record
 base=a.baseline.read_bytes()
 require(len(base)==0x1000000 and sha(base)=='524a5fc3aa4bba634a373a82bed384969104d26778d192e8e8feca7b9b1407d2','Wrong delivered .106 baseline')
 oldfs=base[0x2f0000:0x800000];old=read_image(oldfs,0x510000);files=dict(old)
 require(len(old)==107 and sum(n.endswith('.elf') for n in old)==43,'Wrong .106 inventory')
 meta=json.loads(old['cohort.json']);require(meta['version']=='0.1.106','Wrong baseline version')
 fw=base[0x10000:0x10000+meta['firmware_size']]
 require(sha(fw)==meta['firmware_sha256']=='3242bc4ac994a9b60ab73588955b311508e221d092b8cbc270d9136c608ec026','Native firmware mismatch')
 original_record=parse_record(base[0xff2000:0xff2060],True)
 require(original_record[6]==hashlib.sha256(fw).digest() and original_record[7]==hashlib.sha256(oldfs).digest(),'Baseline bank mismatch')
 manifest=json.loads((a.home/'default.json').read_bytes());before=json.loads(old['default.json'])
 require(before['version']=='0.4.17' and manifest['version']=='0.4.18','Home version must advance')
 require(dict(manifest,version=before['version'])==before,'Home capability/identity change')
 files['default.elf']=(a.home/'default.elf').read_bytes()
 files['default.json']=(json.dumps(manifest,indent=2)+'\n').encode()
 meta.update(version='0.1.107',source_revision=a.system_commit)
 files['cohort.json']=(json.dumps(meta,separators=(',',':'))+'\n').encode()
 order=[]
 for block in range(len(oldfs)//4096):
  for entry in range(15):
   oid=struct.unpack_from('<H',oldfs,block*4096+entry*2)[0]
   if oid in (0,65535) or not oid&0x8000: continue
   off=(block*16+1+entry)*256;actual,span,flags=struct.unpack_from('<HHB',oldfs,off)
   if span: continue
   order.append((oid&0x7fff,oldfs[off+13:off+45].split(b'\0')[0].decode().lstrip('/')))
 order=[name for oid,name in sorted(order)]
 require(len(order)==len(old) and set(order)==set(old),'Invalid baseline SPIFFS order')
 require(sha(a.spiffsgen.read_bytes())=='5779792a4d98a12383233267511735769a201b5c2c79b582186a40c22b7c6466','Wrong SPIFFS generator')
 spec=importlib.util.spec_from_file_location('spiffsgen',a.spiffsgen);sg=importlib.util.module_from_spec(spec);spec.loader.exec_module(sg)
 config=dict(page_size=256,page_ix_len=2,block_size=4096,block_ix_len=2,meta_len=4,obj_name_len=32,obj_id_len=2,span_ix_len=2,packed=True,aligned=True,endianness='little',use_magic=True,use_magic_len=True,aligned_obj_ix_tables=False)
 def pack(values):
  fs=sg.SpiffsFS(0x510000,sg.SpiffsBuildConfig(**config))
  with tempfile.TemporaryDirectory() as tmp:
   for i,n in enumerate(order):
    q=Path(tmp)/str(i);q.write_bytes(values[n]);fs.create_file('/'+n,str(q))
  require(fs.remaining_blocks>=2,'Insufficient SPIFFS spare blocks')
  return fs.to_binary(),fs.remaining_blocks
 require(pack(old)[0]==oldfs,'Generator does not reproduce .106 store byte-for-byte')
 fs,free=pack(files);require(pack(files)==(fs,free),'Nondeterministic SPIFFS output')
 require(read_image(fs,0x510000)==files,'SPIFFS extraction mismatch')
 changed=sorted(n for n in old if files[n]!=old[n])
 require(changed==['cohort.json','default.elf','default.json'],'Unexpected changed files')
 boot=json.loads(files['boot.json'])
 row=next(x for x in boot['app_capabilities'] if x['manifest']=='obd_test.json')
 require(row['image_source']['path']=='Apps/obd-test/obd_test.elf' and 'obd_test.elf' in boot['resident_shell']['foreground'],'OBDTest registration lost')
 bank=initial_bank_state(fw,fs,True);record=parse_record(bank[:96],True)
 require(record[6]==hashlib.sha256(fw).digest() and record[7]==hashlib.sha256(fs).digest(),'New bank mismatch')
 image=bytearray(base);image[0x2f0000:0x800000]=fs;image[0xff2000:0xff3000]=bank[:4096]
 ranges=[(0,0x2f0000),(0x800000,0xff2000),(0xff3000,0x1000000)]
 require(all(image[lo:hi]==base[lo:hi] for lo,hi in ranges),'Unrelated flash change')
 a.output.mkdir(parents=True,exist_ok=True)
 target=a.output/'X4-0.1.107-RTC-Reconciliation-full-0x0.bin';target.write_bytes(image)
 require(target.read_bytes()==image,'Disk readback mismatch')
 store=a.output/'store';store.mkdir(exist_ok=True)
 for n,b in files.items():
  q=store/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 report=dict(version='0.1.107',home_version='0.4.18',baseline_image_sha256=sha(base),image_sha256=sha(image),image_bytes=len(image),system_commit=a.system_commit,runtime_commit='a91edf3fada6a559ec107186dd163d0c8da10d29',native_sha256=sha(fw),native_unchanged=True,settings_partitions_unchanged=True,boot_registration_unchanged=True,obd_test_preserved=True,sd_changes_required=False,store_files=len(files),internal_elfs=43,unchanged_internal_elfs=42,changed_files=changed,free_spiffs_blocks=free,baseline_store_reproduced=True,store_sha256=sha(fs),bank_sector_sha256=sha(bank[:4096]),spiffsgen_sha256=sha(a.spiffsgen.read_bytes()),hardware_tested=False,full_flash_overwrites_user_data=True,unchanged_flash_ranges=[{'start':hex(lo),'end':hex(hi),'sha256':sha(image[lo:hi])} for lo,hi in ranges],inventory={n:sha(b) for n,b in sorted(files.items())})
 (a.output/'assembly-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='inventory'},indent=2))

if __name__=='__main__': main()
