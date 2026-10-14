from pathlib import Path
import argparse,sys,json,hashlib,subprocess,shutil
p=argparse.ArgumentParser()
for n in ['product','baseline','baseline-sd','runtime','watch-product','output']:p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest();sys.path.insert(0,str(a.runtime/'scripts'));from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
sys.path.insert(0,str(a.watch_product/'scripts'));import current_bootfs
raw=a.baseline.read_bytes();assert sha(raw)=='77fc8f87f1c4f825a35e17d65c7bf663b82bbab3be9f8f0f6973581529818b00'
store=read_image(raw[0x2f0000:0x800000],0x510000);before=dict(store);cohort=json.loads(store['cohort.json']);assert cohort['version']=='0.1.111'
cohort['version']='0.1.112';cohort['source_revision']=subprocess.check_output(['git','-C',str(a.product),'rev-parse','HEAD'],text=True).strip();store['cohort.json']=(json.dumps(cohort,indent=2)+'\n').encode()
assert json.loads(store['panel/manifest.json'])['version']=='0.1.12';assert sha(store['panel/driver.elf'])=='3fe67b0b8b22b739b4cee6cb5d8e5da9536883ae567b6d61b142de5da50181d4'
fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
image,packing=current_bootfs.build(store,size=0x510000);assert read_image(image,0x510000)==store
state=initial_bank_state(fw,image,True);record=parse_record(state[:96],True);assert record[6]==hashlib.sha256(fw).digest() and record[7]==hashlib.sha256(image).digest()
full=bytearray(raw);full[0x2f0000:0x800000]=image;full[0xff2000:0xff3000]=state[:4096]
assert all(full[lo:hi]==raw[lo:hi] for lo,hi in [(0,0x2f0000),(0x800000,0xff2000),(0xff3000,0x1000000)])
assert [n for n in store if store[n]!=before[n]]==['cohort.json']
a.output.mkdir(parents=True,exist_ok=True);name='X4-0.1.112-ordered-input-parity-factory-erases-data-0x0.bin';(a.output/name).write_bytes(full)
for n,b in store.items():f=a.output/'store'/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
sd=a.baseline_sd.read_bytes();assert sha(sd)=='de2a7453c3d6769f8e96b5945e76599dbd1257d9adf194c6134278bb3d8033b2';sdname='X4-0.1.112-Cumulative-Changed-SD-Keep-Existing.zip';(a.output/sdname).write_bytes(sd)
proof={'version':'0.1.112','file':name,'bytes':len(full),'sha256':sha(full),'source_revision':cohort['source_revision'],'changed_files':['cohort.json'],'component_versions':{'panel':'0.1.12'},'all_executables_unchanged':True,'native_firmware_unchanged':True,'home_clock_boot_unchanged':True,'sd_file':sdname,'sd_sha256':sha(sd),'sd_new_changes':False,'sd_description':'Cumulative overlay from .111 retained byte-for-byte; no new input fix needed in X4 binaries','packing':packing,'hardware_verified':False,'inventory':{n:sha(b) for n,b in store.items()}}
(a.output/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:v for k,v in proof.items() if k!='inventory'},indent=2))
