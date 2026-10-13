from pathlib import Path
import sys,json,struct,hashlib,importlib.util,copy,tempfile,shutil
w=Path(__file__).parent;r=w.parent;sys.path.insert(0,str(w/'Runtime/scripts'))
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
base=Path('/mnt/data/x4-home-recovery/X4-0.1.105-Home-Startup-Fix-full-0x0.bin').read_bytes();oldfs=base[0x2f0000:0x800000];old=read_image(oldfs,0x510000);files=dict(old)
assert len(base)==0x1000000
order=[]
for block in range(len(oldfs)//4096):
 for entry in range(15):
  oid=struct.unpack_from('<H',oldfs,block*4096+entry*2)[0]
  if oid in (0,65535) or not oid&0x8000:continue
  off=(block*16+1+entry)*256;actual,span,flags=struct.unpack_from('<HHB',oldfs,off)
  if span:continue
  name=oldfs[off+13:off+45].split(b'\0')[0].decode().lstrip('/');order.append((oid&0x7fff,name))
order=[name for oid,name in sorted(order)];assert set(order)==set(old)
boot=json.loads(old['boot.json']);row=next(x for x in boot['app_capabilities'] if x['manifest']=='obd_dashboard.json');test=copy.deepcopy(row);test['manifest']='obd_test.json';test['image_source']['path']='Apps/obd-test/obd_test.elf';boot['app_capabilities'].append(test)
boot['resident_shell']['foreground'].append('obd_test.elf')
manifest=(w/'Utilities/Apps/obd_test.json').read_bytes();files['obd_test.json']=manifest
files['boot.json']=(json.dumps(boot,separators=(',',':'),sort_keys=True)+'\n').encode()
meta=json.loads(old['cohort.json']);assert meta['version']=='0.1.105';meta['version']='0.1.106';files['cohort.json']=(json.dumps(meta,separators=(',',':'))+'\n').encode()
# Keep original relative placement order, insert new metadata ahead of default.
order.insert(order.index('default.elf'),'obd_test.json')
spec=importlib.util.spec_from_file_location('spiffsgen',w/'sources/esp-idf-spiffs/spiffsgen.py');sg=importlib.util.module_from_spec(spec);spec.loader.exec_module(sg)
config=dict(page_size=256,page_ix_len=2,block_size=4096,block_ix_len=2,meta_len=4,obj_name_len=32,obj_id_len=2,span_ix_len=2,packed=True,aligned=True,endianness='little',use_magic=True,use_magic_len=True,aligned_obj_ix_tables=False)
def pack():
 fs=sg.SpiffsFS(0x510000,sg.SpiffsBuildConfig(**config))
 with tempfile.TemporaryDirectory() as tmp:
  for i,n in enumerate(order):p=Path(tmp)/str(i);p.write_bytes(files[n]);fs.create_file('/'+n,str(p))
 assert fs.remaining_blocks>=2
 remaining=fs.remaining_blocks
 return fs.to_binary(),remaining
fs,free=pack();assert pack()==(fs,free);assert read_image(fs,0x510000)==files
assert set(files)-set(old)=={'obd_test.json'}
assert {k for k in old if old[k]!=files[k]}=={'boot.json','cohort.json'}
fw=base[0x10000:0x10000+meta['firmware_size']];assert hashlib.sha256(fw).hexdigest()==meta['firmware_sha256']
newbank=initial_bank_state(fw,fs,True);assert parse_record(newbank[:96],True)[7]==hashlib.sha256(fs).digest()
image=bytearray(base);image[0x2f0000:0x800000]=fs;image[0xff2000:0xff3000]=newbank[:4096]
assert image[:0x2f0000]==base[:0x2f0000] and image[0x800000:0xff2000]==base[0x800000:0xff2000] and image[0xff3000:]==base[0xff3000:]
p=r/'X4-0.1.106-OBD-Side-by-Side-full-0x0.bin';p.write_bytes(image)
(r/'registration').mkdir(exist_ok=True);(r/'registration/bootfs0.bin').write_bytes(fs);(r/'registration/bank0-record.bin').write_bytes(newbank[:4096])
s=w/'registered-store';s.mkdir(exist_ok=True)
for n,b in files.items():p=s/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
sd=r/'SD/Apps/obd-test';sd.mkdir(parents=True,exist_ok=True);shutil.copyfile(w/'target-test/obd_test.elf',sd/'obd_test.elf');(sd/'manifest.json').write_bytes(manifest)
def sha(b):return hashlib.sha256(b).hexdigest()
report={'version':'0.1.106','baseline_image_sha256':sha(base),'image_sha256':sha(image),'native_runtime_unchanged':True,'runtime_source':'a91edf3fada6a559ec107186dd163d0c8da10d29','native_sha256':sha(fw),'firmware_size':len(fw),'bootloader_prefix_sha256':sha(base[:0x9000]),'old_store_sha256':sha(oldfs),'new_store_sha256':sha(fs),'new_bank_sector_sha256':sha(newbank[:4096]),'changed_existing_store_files':['boot.json','cohort.json'],'added_store_files':['obd_test.json'],'all_43_internal_elfs_unchanged':True,'original_obd_catalog_policy_unchanged':True,'generic_installation_permissions_unchanged':True,'test_app_id':'obd-test','test_app_sha256':sha((sd/'obd_test.elf').read_bytes()),'store_files':len(files),'free_spiffs_blocks':free,'spiffs_config':config,'ordered_paths':order,'hardware_tested':False}
(r/'build-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='ordered_paths'},indent=2))
