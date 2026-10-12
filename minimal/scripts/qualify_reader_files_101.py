#!/usr/bin/env python3
"""Admit all .101 internal/SD images and exercise OBD and Hollow catalog paths."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from package_reader_bin_overlay import compile_admission,native_witness,imports,sha
from compose_shared_settings_090 import audit_selected_images,git,tree
from test_obd_native_catalog import run as obd_catalog
from test_hollow_native_catalog import run as hollow_catalog

p=argparse.ArgumentParser(description=__doc__)
for n in ('runtime','tools','delivery','output'):p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
a=p.parse_args();store=a.delivery/'store';sd=a.delivery/'SD'
receipt=json.loads((a.delivery/'receipts/reader-files-composition.json').read_text())
assert git(a.runtime,'rev-parse','HEAD')==receipt['runtime_commit'] and git(a.runtime,'rev-parse','HEAD^{tree}')==receipt['runtime_tree'] and not git(a.runtime,'status','--porcelain')
assert tree(store)==receipt['store'] and tree(sd)==receipt['sd']
raw=(a.delivery/'components/firmware.bin').read_bytes();assert sha(raw)==receipt['firmware_sha256']
assert ('RTE_SOURCE='+receipt['runtime_commit']).encode()+b'\0' in raw
a.output.mkdir(parents=True,exist_ok=False)
sys.path[:0]=[str(a.tools/'scripts'),str(a.runtime/'scripts')]
exports,witness=native_witness(a.runtime,(a.delivery/'components/firmware.bin').read_bytes())
selected=audit_selected_images(json.loads((store/'boot.json').read_text()),store,sd);assert len(selected)==48
internal=[dict(path=str(p.relative_to(store)),role='driver' if p.name=='driver.elf' else 'app',sha256=sha(p.read_bytes())) for p in sorted(store.rglob('*.elf'))];assert len(internal)==43
assert selected==receipt['selected_sd_images']
env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0')
for name,sanitized in [('normal',False),('asan-ubsan',True)]:
 d=a.output/name
 info=compile_admission(a.runtime,a.tools,d,exports,sanitized,installed_catalog=True,shared_files=True,provider_capacity=40,native_usb_phy=True)
 for root,rows in [(store,internal),(sd,selected)]:
  for row in rows:
   path=root/row['path'];assert not(set(imports(path.read_bytes()))-set(exports))
   subprocess.run([str(d/'strict'),row['role'],str(path)],check=True,env=env)
 result=subprocess.run([str(d/'cohort'),str(store),str(store)],check=True,env=env,capture_output=True,text=True)
 admitted=json.loads(result.stdout);assert admitted['prepared'] and admitted['cohort_validated'] and admitted['elf_count']==43 and admitted['hardware_calls']==admitted['storage_calls']==0
 info.update(admission=admitted,selected_sd_images=selected,internal_images=internal,native=witness,physical_hardware_tested=False)
 (d/'result.json').write_text(json.dumps(info,indent=2)+'\n')
 obd_catalog(a.runtime,a.tools,d,store,a.output/('obd-catalog-'+name),sanitize=sanitized)
 hollow_catalog(a.runtime,a.tools,d,store,a.output/('hollow-catalog-'+name),sanitize=sanitized)
 print(name,'43 internal + 48 selected SD + exact OBD/Hollow native catalogs PASS',flush=True)
