#!/usr/bin/env python3
"""Update only Game Boy on the exact .119 cumulative X4 baseline."""
from pathlib import Path
import argparse,json,hashlib,subprocess,sys,zipfile
p=argparse.ArgumentParser()
for n in ('baseline','previous-sd','runtime','watch','shared','app','product-repo','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(a.runtime.resolve()/'scripts'),str(a.watch.resolve()/'scripts'),str(a.shared.resolve()/'scripts')]
from spiffs_image import read_image
from paired_bank_images import initial_bank_state,parse_record
from normalize_xtensa_relocations import normalize
from compact_current_elf import compact
import current_bootfs
sha=lambda b:hashlib.sha256(b).hexdigest();enc=lambda v:(json.dumps(v,separators=(',',':'))+'\n').encode()
base_sha='64de9c77b3a6e1a113d256820f16ac71a831bda47a5b7594a089e5063b121b42';raw=a.baseline.read_bytes();assert len(raw)==0x1000000 and sha(raw)==base_sha
before=read_image(raw[0x2f0000:0x800000],0x510000);assert current_bootfs.build(before,size=0x510000)[0]==raw[0x2f0000:0x800000]
receipt=json.loads((a.app/'build.json').read_bytes());assert not receipt['dirty'] and receipt['version']=='1.3.25'
app=(a.app/'gameboy.elf').read_bytes();assert sha(app)==receipt['elf']['sha256']
elf=a.output/'gameboy.elf';elf.write_bytes(app);normalize(elf)
compaction=compact(elf,str(Path.home()/'.platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-gcc'),debug_path=a.output/'debug-gameboy.elf')
manifest=json.loads((a.app/'gameboy.json').read_bytes());prior=json.loads(before['gameboy.json']);assert prior['version']=='1.3.24'
assert {k:v for k,v in prior.items() if k!='version'}=={k:v for k,v in manifest.items() if k!='version'}
store=dict(before);store['gameboy.json']=enc(manifest)
cohort=json.loads(before['cohort.json']);assert cohort['version']=='0.1.119';fw=raw[0x10000:0x10000+cohort['firmware_size']];assert sha(fw)==cohort['firmware_sha256']
head=subprocess.check_output(['git','-C',a.product_repo,'rev-parse','HEAD'],text=True).strip();cohort.update(version='0.1.120',source_revision=head);store['cohort.json']=enc(cohort)
image,packing=current_bootfs.build(store,size=0x510000);assert read_image(image,0x510000)==store
state=initial_bank_state(fw,image,True);parse_record(state[:96],True)
full=bytearray(raw);full[0x2f0000:0x800000]=image;full[0xff2000:0xff2000+len(state)]=state
assert full[:0x2f0000]==raw[:0x2f0000] and full[0x800000:0xff2000]==raw[0x800000:0xff2000] and full[0xff3000:]==raw[0xff3000:]
changed=sorted(n for n in store if store[n]!=before[n]);assert changed==['cohort.json','gameboy.json']
assert sha(a.previous_sd.read_bytes())=='e25e58bf028aa50a8b3287987c326e48ee3f2723df2d6686e60c3533c1157d2a'
with zipfile.ZipFile(a.previous_sd) as z:sd={n:z.read(n) for n in z.namelist()}
oldsd=dict(sd);sd.update({'Apps/gameboy/gameboy.elf':elf.read_bytes(),'Apps/gameboy/manifest.json':enc(manifest)})
assert all(sd[n]==b for n,b in oldsd.items())
sdname='X4-0.1.120-Cumulative-Changed-SD-Keep-Existing.zip'
for name,files in [(sdname,sd),('GameBoy-1.3.25-SD-only.zip',{n:b for n,b in sd.items() if n.startswith('Apps/gameboy/')})]:
 with zipfile.ZipFile(a.output/name,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in sorted(files.items()):z.writestr(n,b)
 with zipfile.ZipFile(a.output/name) as z:assert {n:z.read(n) for n in z.namelist()}==files
name='X4-0.1.120-T060-GameBoy-State-factory-erases-data-0x0.bin';(a.output/name).write_bytes(full)
for n,b in store.items():q=a.output/'store'/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
proof=dict(file=name,version='0.1.120',image_sha256=sha(full),baseline_sha256=base_sha,product_commit=head,app_source=receipt['source'],app_sha256=sha(elf.read_bytes()),app_bytes=elf.stat().st_size,sd_file=sdname,sd_sha256=sha((a.output/sdname).read_bytes()),native_sha256=sha(fw),native_unchanged=True,boot_grants_unchanged=True,all_other_store_files_unchanged=True,previous_changed_sd_files_unchanged=True,changed_store_files=changed,packing=packing,compaction=compaction,hardware_tested=False)
(a.output/'assembly-report.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
