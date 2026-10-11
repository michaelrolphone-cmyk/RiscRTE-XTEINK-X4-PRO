#!/usr/bin/env python3
"""Qualify MSC 0.1.7 and SD 0.2.16 over combined .078 and cleanup .1.6; no firmware."""
import argparse, hashlib, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path

def sha(data): return hashlib.sha256(data).hexdigest()
def inventory(path): return {p.relative_to(path).as_posix():sha(p.read_bytes()) for p in sorted(path.rglob('*')) if p.is_file()}
p=argparse.ArgumentParser(description=__doc__)
for name in ('baseline','target','sd-target','cleanup-store','reader','runtime','tools','output'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--sanitizers',default='undefined')
a=p.parse_args();a.output=a.output.resolve();assert not a.output.exists();a.output.mkdir(parents=True)
sys.path[:0]=[str(a.reader/'scripts'),str(a.tools/'scripts'),str(a.runtime/'scripts')]
from read_only_spiffs import read_image
from package_reader_bin_overlay import compile_admission, imports, native_witness, RUNTIME_TREE
from generate_provider_package_inputs_v1 import prepare
from verify_provider_relocation_map import audit_loader_map
from build_installed_usb_stack import entry
from pack_rte_zip import pack_directory, catalog_row
baseline_image=a.baseline/'X4-0.1.78-Reader-Daily-Paper-Panel-0.1.12-full-0x0.bin'
raw=baseline_image.read_bytes();assert sha(raw)=='1d24836ca58c1f6ca841d3d9a41c38a3ad459e95746760de363a32e5ba04e7b5'
assert subprocess.check_output(['git','-C',a.runtime,'rev-parse','HEAD^{tree}'],text=True).strip()==RUNTIME_TREE
assert not subprocess.check_output(['git','-C',a.runtime,'status','--porcelain','--untracked-files=no'],text=True)
files=read_image(raw[0x2f0000:0x800000],0x510000)
assert sha(files['usb-msc/driver.elf'])=='f791783ac4e21d61c0da4576aef091af2d218d7cd84c4e6ac2f0f36b09a00dac'
for label in ('baseline-store','store'):
 for name,data in files.items():
  dest=a.output/label/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
# Verify the exact delivered SD archive before staging every external application.
sd_zip=a.baseline/'X4-0.1.78-Reader-Daily-Paper-SD.zip'
receipt=json.loads((a.baseline/'build-custody.json').read_text())
assert sha(sd_zip.read_bytes())=='b7e504f16d717df839f974f0dde6e5f33cf9ff303e49fbb7936784447298d2e8'
with zipfile.ZipFile(sd_zip) as z:
 assert z.testzip() is None
 for name in z.namelist():
  if name.startswith(('Apps/','fonts/')) and not name.endswith('/'):
   assert '..' not in Path(name).parts
   dest=a.output/'sd'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
assert len(list((a.output/'sd').rglob('*.elf')))==16
proof=json.loads((a.target/'target-proof.json').read_text())
assert proof['reader_commit']==subprocess.check_output(['git','-C',a.reader,'rev-parse','HEAD'],text=True).strip()
assert not proof['source_dirty'] and proof['target_structure_passed']
assert sha((a.target/'driver.elf').read_bytes())==proof['elf_sha256']
manifest=(a.reader/'Drivers/usb_device_msc_esp32s3/manifest.json').read_bytes();m=json.loads(manifest)
assert m['id']=='usb-device-msc-esp32s3' and m['version']=='0.1.7'
assert (a.target/'manifest.json').read_bytes()==manifest
# Compact with the same verified loader-metadata-v3 transform used by .078.
from compact_current_elf import compact
cc=os.environ['NATIVE_DRIVER_CC'];dest=a.output/'store/usb-msc/driver.elf';shutil.copyfile(a.target/'driver.elf',dest)
compaction=compact(dest,cc,debug_path=a.output/'debug-original.elf')
(a.output/'store/usb-msc/manifest.json').write_bytes(manifest)
sd_proof=json.loads((a.sd_target/'build.json').read_text())
sd_manifest=(a.sd_target/'manifest.json').read_bytes();sm=json.loads(sd_manifest)
assert sm['id']=='x4pro-sd' and sm['version']=='0.2.16'
assert sha((a.sd_target/'driver.elf').read_bytes())==sd_proof['sha256']
sd_dest=a.output/'store/sd/driver.elf';shutil.copyfile(a.sd_target/'driver.elf',sd_dest)
sd_compaction=compact(sd_dest,cc,debug_path=a.output/'sd-debug-original.elf')
(a.output/'store/sd/manifest.json').write_bytes(sd_manifest)
changes=[name for name,data in files.items() if (a.output/'store'/name).read_bytes()!=data]
assert sorted(changes)==['sd/driver.elf','sd/manifest.json','usb-msc/driver.elf','usb-msc/manifest.json']
# Independently bind the prior completed cleanup checkpoint and preserve every
# other combined .078 payload in that active-source cohort too.
shutil.copytree(a.cleanup_store,a.output/'cleanup-store')
cleanup_changes=[name for name,data in files.items() if (a.output/'cleanup-store'/name).read_bytes()!=data]
assert sorted(cleanup_changes)==['usb-msc/driver.elf','usb-msc/manifest.json']
assert sha((a.output/'cleanup-store/usb-msc/driver.elf').read_bytes())=='dd045f3a828048e82d14676757e54a6dab06d01e00b6a3711d28172b4f8ce567'
assert json.loads((a.output/'cleanup-store/usb-msc/manifest.json').read_text())['version']=='0.1.6'
catalog={'schema':1,'release':'unpublished-msc-sd-batching-078','packages':[]};mappings={}
for elf,manifest_path,meta_manifest in ((dest,a.target/'manifest.json',m),(sd_dest,a.sd_target/'manifest.json',sm)):
 mapping=audit_loader_map(elf);mappings[meta_manifest['id']]=mapping
 assert not any(mapping[k] for k in ('unmapped_relocations','unmapped_relative_values','unmapped_executable_sections','absolute_peripheral_relocations'))
 package=a.output/'package'/meta_manifest['id'];package.mkdir(parents=True);shutil.copyfile(elf,package/'driver.elf')
 prepare(package/'driver.elf',manifest_path,package)
 meta={'schema':1,'kind':'driver','id':meta_manifest['id'],'version':meta_manifest['version'],'artifact':'driver.elf','architecture':meta_manifest['architecture'],'min_runtime_api':2,'entries':[entry(package/n,n=='driver.elf') for n in ('driver.elf','provider-abi.v1','privileged-imports.v1')],'requires':[{'capability':r['capability'],'min_api':r['api']} for r in meta_manifest['requires']]}
 (package/'.package.json').write_text(json.dumps(meta,separators=(',',':'))+'\n')
 name='driver-'+meta_manifest['id']+'-'+meta_manifest['version']+'-xtensa-esp32s3.rte.zip';archive=pack_directory(package)
 assert archive==pack_directory(package);(a.output/name).write_bytes(archive)
 catalog['packages'].append(catalog_row(package,name,archive))
(a.output/'package-catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
native=(a.baseline/'native.bin').read_bytes();exported,witness=native_witness(a.runtime,native)
results=[]
for sanitizer in (None,a.sanitizers):
 mode='plain' if sanitizer is None else 'sanitized';out=a.output/mode
 admission=compile_admission(a.runtime,a.tools,out,exported,sanitizer is not None,sanitizer or 'undefined')
 modules=[(f,f.name=='driver.elf') for f in (a.output/'store').rglob('*.elf')]+[(f,False) for f in (a.output/'sd').rglob('*.elf')]
 assert len(modules)==54
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1')
 for f,driver in modules:
  assert set(imports(f.read_bytes()))<=set(exported)
  cmd=[str(out/'strict'),'driver' if driver else 'app',str(f)];subprocess.run(cmd,check=True,env=env,timeout=30)
  if f in (dest,sd_dest):
   for symbol in imports(f.read_bytes()):subprocess.run(cmd+[symbol],check=True,env=env,timeout=30)
 for active in ('baseline-store','cleanup-store','store'):
  r=subprocess.run([str(out/'cohort'),str(a.output/active),str(a.output/'store')],check=True,capture_output=True,text=True,env=env,timeout=60)
  row=json.loads(r.stdout);assert row['prepared'] and row['cohort_validated'] and row['elf_count']==38 and row['hardware_calls']==row['storage_calls']==0
  (out/(active+'-to-candidate.json')).write_text(r.stdout);results.append({'mode':mode,'active':active,**row})
 print(mode+': 54 modules, MSC/SD missing-import negatives and three cohort admissions PASS',flush=True)
record={'schema':'msc-sd-batching-078-target-qualification','baseline_image_sha256':sha(raw),'baseline_sd_sha256':sha(sd_zip.read_bytes()),'reader_commit':proof['reader_commit'],'target_proof':proof,'compaction':compaction,'sd_target_proof':sd_proof,'sd_compaction':sd_compaction,'loader_mapping':mappings,'changed_store_paths':sorted(changes),'baseline_store_inventory':inventory(a.output/'baseline-store'),'candidate_store_inventory':inventory(a.output/'store'),'sd_inventory':inventory(a.output/'sd'),'packages':catalog['packages'],'cohort_results':results,'native_export_witness':witness,'hardware_tested':False,'full_firmware_emitted':False}
(a.output/'qualification.json').write_text(json.dumps(record,indent=2)+'\n')
