#!/usr/bin/env python3
"""Strict target ELF/import and native store metadata admission; no execution."""
import argparse,json,subprocess,sys,shutil,copy
from pathlib import Path
from package_reader_bin_overlay import native_witness,compile_admission,imports,sha
p=argparse.ArgumentParser(description=__doc__)
for name in ('runtime','tools','native-bin','store','output'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--provider-capacity',type=int,choices=[29,32,40],default=29)
p.add_argument('--shared-files',action='store_true')
a=p.parse_args();a.runtime=a.runtime.resolve();a.tools=a.tools.resolve();a.native_bin=a.native_bin.resolve();a.store=a.store.resolve();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.runtime.resolve()/'scripts'));sys.path.insert(0,str(a.tools.resolve()/'scripts'))
exports,witness=native_witness(a.runtime,a.native_bin.read_bytes())
info=compile_admission(a.runtime,a.tools,a.output/'ubsan',exports,True,'undefined',installed_catalog=True,shared_files=a.shared_files,provider_capacity=a.provider_capacity)
modules=[]
for path in sorted(a.store.rglob('*.elf')):
 provider=path.name=='driver.elf';needed=imports(path.read_bytes())
 if set(needed)-set(exports):raise ValueError('Unresolved imports: '+str(path))
 command=[str(a.output/'ubsan/strict'),'driver'if provider else'app',str(path)]
 subprocess.run(command,check=True)
 modules.append(dict(path=str(path.relative_to(a.store)),sha256=sha(path.read_bytes())))
result=subprocess.run([str(a.output/'ubsan/cohort'),str(a.store),str(a.store)],capture_output=True,text=True,check=True)
print(result.stdout);print(result.stderr,file=sys.stderr)
admission=json.loads(result.stdout)
if not(admission['prepared']and admission['cohort_validated']and admission['elf_count']==len(modules)and admission['hardware_calls']==admission['storage_calls']==0):raise ValueError(admission)
negative=a.output/'changed-store';shutil.copytree(a.store,negative);original=json.loads((negative/'boot.json').read_text());rejections=[]
for case in ('range-moved','range-removed','cache-owner-moved','settings-disabled'):
 boot=copy.deepcopy(original)
 if case=='range-moved':boot['installation']['namespace_range']['first']+=1
 elif case=='range-removed':del boot['installation']['namespace_range']
 elif case=='settings-disabled':boot['installation']['settings_sd']=False
 else:next(x for x in boot['drivers'] if x['manifest']=='installed-apps/manifest.json')['app_data'][0]['namespace']+=1
 (negative/'boot.json').write_text(json.dumps(boot))
 result=subprocess.run([str(a.output/'ubsan/cohort'),str(a.store),str(negative)],capture_output=True,text=True,check=True)
 row=json.loads(result.stdout)
 if not(row['prepared']and not row['cohort_validated']and row['hardware_calls']==row['storage_calls']==0):raise ValueError((case,row))
 rejections.append(case)
info.update(native=witness,modules=modules,admission=admission,rejected_namespace_changes=rejections,hardware_tested=False,scope='Actual native ELF role/import admission and Runtime metadata; provider/application execution is not tested here.')
(a.output/'evidence.json').write_text(json.dumps(info,indent=2)+'\n')
