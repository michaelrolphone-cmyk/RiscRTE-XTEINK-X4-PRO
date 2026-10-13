#!/usr/bin/env python3
"""Compose Points 0.6.18 over the exact qualified X4 0.1.108 image.

No hardware access. Keep all unrelated logical files and flash ranges unchanged.
"""
import argparse,hashlib,importlib.util,json,struct,sys,tempfile,zipfile
from pathlib import Path

def sha(data): return hashlib.sha256(data).hexdigest()
def require(ok,message):
 if not ok: raise ValueError(message)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('baseline','points','baseline-sd','runtime','spiffsgen','output'):
  p.add_argument('--'+n,required=True,type=Path)
 p.add_argument('--product-commit',required=True)
 a=p.parse_args();sys.path.insert(0,str(a.runtime/'scripts'))
 from spiffs_image import read_image
 from paired_bank_images import initial_bank_state,parse_record
 base=a.baseline.read_bytes()
 require(len(base)==0x1000000 and sha(base)=='9a55a27d0ad689295eacd248a378f54577ce2997fea51454304bdd70effae835','Wrong qualified .108 baseline')
 oldfs=base[0x2f0000:0x800000];old=read_image(oldfs,0x510000);files=dict(old)
 require(len(old)==107 and sum(n.endswith('.elf') for n in old)==43,'Wrong .108 inventory')
 meta=json.loads(old['cohort.json']);require(meta['version']=='0.1.108','Wrong baseline version')
 fw=base[0x10000:0x10000+meta['firmware_size']]
 require(sha(fw)==meta['firmware_sha256']=='3242bc4ac994a9b60ab73588955b311508e221d092b8cbc270d9136c608ec026','Native firmware mismatch')
 original_record=parse_record(base[0xff2000:0xff2060],True)
 require(original_record[6]==hashlib.sha256(fw).digest() and original_record[7]==hashlib.sha256(oldfs).digest(),'Baseline bank mismatch')
 manifest=json.loads((a.points/'points_in_time.json').read_bytes());before=json.loads(old['points_in_time.json'])
 require(before['version']=='0.6.17' and manifest['version']=='0.6.18','Points version must advance')
 require(dict(manifest,version='0.6.17')=={k:v for k,v in before.items() if k!='runtime_lifecycle'},'Points authority or identity changed')
 require(before.get('runtime_lifecycle')=='foreground','Wrong deployed Points lifecycle')
 manifest=dict(before,version=manifest['version'])
 rf=(a.points/'points_in_time.elf').read_bytes();digest=sha(rf)
 require(digest=='cbc08f8c5846967b7c9cdc5cae4f832e2a0ec7c8a3534d565eebef804ae92a2d','Wrong qualified X4 Points target')
 files['points_in_time.json']=(json.dumps(manifest,indent=2)+'\n').encode()
 original_boot=json.loads(old['boot.json']);boot=json.loads(old['boot.json'])
 row=next(x for x in boot['app_capabilities'] if x['manifest']=='points_in_time.json')
 require(row['image_source']=={'path':'Apps/points_in_time/points_in_time.elf','volume_instance':9},'Wrong Points predecessor selection')
 directory='Apps/points_in_time/image-'+digest;row['image_source']['path']=directory+'/points_in_time.elf'
 files['boot.json']=(json.dumps(boot,separators=(',',':'),sort_keys=True)+'\n').encode()
 row['image_source']['path']='Apps/points_in_time/points_in_time.elf'
 require(boot==original_boot,'Unrelated boot authority mutation')
 meta.update(version='0.1.109',source_repo='michaelrolphone-cmyk/RiskRTE-XTEINK-X4-PRO',source_revision=a.product_commit)
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
  free=fs.remaining_blocks
  return fs.to_binary(),free
 require(pack(old)[0]==oldfs,'Generator does not reproduce .108 store byte-for-byte')
 fs,free=pack(files);require(pack(files)==(fs,free),'Nondeterministic SPIFFS output')
 require(read_image(fs,0x510000)==files,'SPIFFS extraction mismatch')
 changed=sorted(n for n in old if files[n]!=old[n])
 require(changed==['boot.json','cohort.json','points_in_time.json'],'Unexpected changed files')
 boot=json.loads(files['boot.json'])
 row=next(x for x in boot['app_capabilities'] if x['manifest']=='obd_test.json')
 require(row['image_source']['path']=='Apps/obd-test/obd_test.elf' and 'obd_test.elf' in boot['resident_shell']['foreground'],'OBDTest registration lost')
 bank=initial_bank_state(fw,fs,True);record=parse_record(bank[:96],True)
 require(record[6]==hashlib.sha256(fw).digest() and record[7]==hashlib.sha256(fs).digest(),'New bank mismatch')
 image=bytearray(base);image[0x2f0000:0x800000]=fs;image[0xff2000:0xff3000]=bank[:4096]
 ranges=[(0,0x2f0000),(0x800000,0xff2000),(0xff3000,0x1000000)]
 require(all(image[lo:hi]==base[lo:hi] for lo,hi in ranges),'Unrelated flash change')
 a.output.mkdir(parents=True,exist_ok=True)
 target=a.output/'X4-0.1.109-Points-Modal-Policy-full-0x0.bin';target.write_bytes(image)
 require(target.read_bytes()==image,'Disk readback mismatch')
 store=a.output/'store';store.mkdir(exist_ok=True)
 for n,b in files.items():
  q=store/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 require(sha(a.baseline_sd.read_bytes())=='687ad13059b36c6f3841cf36f2eeaa7f7c0452145bf8511d91651da9b8315940','Wrong preserved .108 RF overlay')
 with zipfile.ZipFile(a.baseline_sd) as z:sd={n:z.read(n) for n in z.namelist()}
 require(len(sd)==2 and all(n.startswith('Apps/waterfall/image-') for n in sd),'Unexpected RF overlay')
 previous_sd=dict(sd)
 sd.update({directory+'/points_in_time.elf':rf,directory+'/manifest.json':files['points_in_time.json']})
 require(len(sd)==4 and all(sd[n]==b for n,b in previous_sd.items()),'RF overlay changed')
 for name,data in sd.items():
  path=a.output/'SD'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 archive=a.output/'X4-0.1.109-Cumulative-Changed-SD-Keep-Existing.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in sorted(sd.items()):
   info=zipfile.ZipInfo(name,date_time=(2026,10,13,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
 with zipfile.ZipFile(archive) as z:require({n:z.read(n) for n in z.namelist()}==sd,'SD ZIP readback differs')
 report=dict(version='0.1.109',points_version='0.6.18',baseline_image_sha256=sha(base),image_sha256=sha(image),image_bytes=len(image),product_commit=a.product_commit,points_system_commit='c4579cdb14f4ce185aed32d5de86f44a25733007',points_utilities_commit='35c2141c68668971dc524d98702109b00c740815',runtime_commit='a91edf3fada6a559ec107186dd163d0c8da10d29',native_sha256=sha(fw),native_unchanged=True,home_unchanged=True,settings_partitions_unchanged=True,boot_authority_unchanged=True,boot_image_selection_changed=['points_in_time.json'],obd_test_preserved=True,store_files=len(files),internal_elfs=43,unchanged_internal_elfs=43,changed_files=changed,free_spiffs_blocks=free,baseline_store_reproduced=True,store_sha256=sha(fs),bank_sector_sha256=sha(bank[:4096]),spiffsgen_sha256=sha(a.spiffsgen.read_bytes()),points_sha256=digest,sd_overlay_sha256=sha(archive.read_bytes()),added_sd_files={n:sha(b) for n,b in sd.items() if n not in previous_sd},packaged_sd_files={n:sha(b) for n,b in sd.items()},rf_overlay_preserved=True,existing_sd_paths_modified=[],full_external_sd_inventory_audited=False,hardware_tested=False,full_flash_overwrites_user_data=True,unchanged_flash_ranges=[{'start':hex(lo),'end':hex(hi),'sha256':sha(image[lo:hi])} for lo,hi in ranges],inventory={n:sha(b) for n,b in sorted(files.items())})
 (a.output/'assembly-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='inventory'},indent=2))

if __name__=='__main__': main()
