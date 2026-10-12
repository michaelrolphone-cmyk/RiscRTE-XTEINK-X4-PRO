#!/usr/bin/env python3
"""Reproduce selected X4 Home, then overlay only the bounded policy promise inputs."""
import argparse,hashlib,json,os,shlex,shutil,subprocess,sys
from pathlib import Path
from build_lists_shared_input import ROOT,DOCS,SYSTEM_BASE,load,clean,git,require,sha
OWNER_VERSION='0.4.15'
OWNER_PRIOR_SHA='85c56071217d603a594514c0eef3a25982c7b03bafe86f1121880db62b3c5bb9'

def build(a):
 S,B,E,O=[getattr(a,n).resolve() for n in ('system','baseline','predecessor_evidence','output')]
 revision=git(ROOT,'rev-parse','HEAD');clean(ROOT,revision);clean(S,a.system_commit)
 subprocess.run(['git','-C',str(S),'merge-base','--is-ancestor',SYSTEM_BASE,a.system_commit],check=True)
 profile=json.loads((DOCS/'owner-selected-profile.json').read_text());require(profile['selected_elf_sha256']==OWNER_PRIOR_SHA and profile['new_version']==OWNER_VERSION,'Wrong owner profile')
 old=(B/'store/default.elf').read_bytes();manifest=json.loads((B/'store/default.json').read_bytes());boot=json.loads((B/'store/boot.json').read_bytes())
 require(hashlib.sha256(old).hexdigest()==OWNER_PRIOR_SHA and manifest['version']=='0.4.14','Wrong selected owner')
 require(boot['default_app']==boot['resident_shell']['host']=='default.elf' and 'lists.elf' in boot['resident_shell']['foreground'],'Wrong resident roles')
 require(sha(E/'committed-inputs.json')==profile['original_input_inventory_sha256'],'Wrong historical dependency receipt')
 require(not O.exists(),'Use fresh owner output');O.mkdir(parents=True)
 cc=os.environ.get('NATIVE_APP_CC') or shutil.which('xtensa-esp32s3-elf-gcc');require(cc,'Compiler required');toolchain=Path(cc).resolve().parents[1]
 origin={'selected-system':a.selected_system.resolve(),'selected-product':a.selected_product.resolve(),'selected-sdk':E/'committed-candidate','toolchain':toolchain}
 require(git(origin['selected-system'],'rev-parse','HEAD^{tree}')==profile['selected_system_tree'],'Wrong selected System source tree')
 require(git(origin['selected-system'],'rev-parse',profile['selected_system_commit']+'^{tree}')==profile['selected_system_tree'],'Wrong published System pin')
 require(git(origin['selected-product'],'rev-parse','HEAD')==profile['selected_product_commit'],'Wrong selected product source')
 staged={k:(v if k=='toolchain' else O/'frozen'/k) for k,v in origin.items()}
 def command():
  result=[]
  for arg in profile['compiler_command']:
   for owner,path in staged.items():arg=arg.replace('{'+owner+'}',str(path))
   result.append(arg)
  return result
 for key,digest in profile['input_hashes'].items():
  owner,relative=key.split(':',1);source=origin[owner]/relative;require(sha(source)==digest,'Historical dependency drift: '+key)
  if owner!='toolchain':dest=staged[owner]/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
 mapping=origin['selected-sdk']/'exports.map';require(sha(mapping)==profile['exports_map_sha256'],'Historical exports changed');shutil.copyfile(mapping,staged['selected-sdk']/'exports.map')
 normalizer=a.relocation_tools.resolve()/'normalize_xtensa_relocations.py';require(sha(normalizer)==profile['normalizer_sha256'],'Relocation normalizer changed')
 compiler=subprocess.check_output([cc,'--version'],text=True).splitlines()[0];require('8.4.0' in compiler and '2021r2-patch5' in compiler,'Wrong compiler')
 results={};actual_deps={};overlay={};cmd=command();elf=staged['selected-sdk']/'default.elf'
 def capture_dependencies():
  actual_deps={}
  compile_flags=[x for x in cmd[1:] if not x.endswith('.c') and x!='-o' and x!=str(elf)]
  for source in [x for x in cmd if x.endswith('.c')]:
   raw=subprocess.check_output([cc,*compile_flags,'-M',source],text=True)
   for token in shlex.split(raw.replace('\\\n',' ').split(':',1)[1]):
    path=Path(token).resolve();matches=[(owner,path.relative_to(root)) for owner,root in staged.items() if path.is_relative_to(root)];require(len(matches)==1,'Unowned owner dependency: '+token);owner,relative=matches[0]
    actual_deps[owner+':'+relative.as_posix()]={'sha256':sha(path),'bytes':path.stat().st_size}
  return actual_deps
 for mode in ('predecessor','continuity','repeat'):
  if mode=='continuity':
   for relative in profile['allowed_source_overlays']:
    source=S/relative;require(source.is_file(),'Missing owner source overlay');overlay[relative]={'sha256':sha(source),'bytes':source.stat().st_size}
    dest=staged['selected-system']/relative if relative.endswith('.inc') else staged['selected-sdk']/'idle-sdk/include'/source.name
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
  subprocess.run(cmd,check=True);subprocess.run([sys.executable,str(normalizer),str(elf)],check=True)
  results[mode]={'sha256':sha(elf),'bytes':elf.stat().st_size}
  if mode=='predecessor':
   require(sha(elf)==OWNER_PRIOR_SHA,'Selected resident owner was not reproduced exactly');predecessor_deps=capture_dependencies()
   prior_actual={k:v['sha256'] for k,v in predecessor_deps.items()};historical=profile['input_hashes']
   require(set(historical)-set(prior_actual)=={'toolchain:xtensa-esp32s3-elf/sys-include/stdint.h','toolchain:xtensa-esp32s3-elf/sys-include/sys/_intsup.h'} and set(prior_actual)-set(historical)=={'toolchain:lib/gcc/xtensa-esp32s3-elf/8.4.0/include/stdint-gcc.h'} and all(prior_actual[k]==historical[k] for k in set(prior_actual)&set(historical)),'Historical vs actual predecessor dependency trace changed')
  if mode=='continuity':shutil.copyfile(elf,O/'default.elf')
 require(results['continuity']==results['repeat'],'Owner target is not reproducible')
 require(results['continuity']['sha256']!=OWNER_PRIOR_SHA,'Owner policy overlay has no compiled effect')
 actual_deps=capture_dependencies()
 expected={k:v['sha256'] for k,v in predecessor_deps.items()}
 for relative,row in overlay.items():expected[('selected-system:'+relative) if relative.endswith('.inc') else 'selected-sdk:idle-sdk/include/'+Path(relative).name]=row['sha256']
 require({k:v['sha256'] for k,v in actual_deps.items()}==expected,'Owner dependency closure differs beyond approved overlay: missing='+str(sorted(set(expected)-set(actual_deps)))+' added='+str(sorted(set(actual_deps)-set(expected)))+' changed='+str([k for k in set(expected)&set(actual_deps) if expected[k]!=actual_deps[k]['sha256']]))
 symbols=subprocess.check_output([cc.removesuffix('gcc')+'nm','-D',str(O/'default.elf')],text=True).splitlines();imports=sorted({x.split()[-1] for x in symbols if ' U ' in ' '+x});exports=sorted({x.split()[-1] for x in symbols if len(x.split())>=3 and x.split()[-2] in ('T','D','B','R')})
 oldsymbols=subprocess.check_output([cc.removesuffix('gcc')+'nm','-D',str(B/'store/default.elf')],text=True).splitlines();require(imports==sorted({x.split()[-1] for x in oldsymbols if ' U ' in ' '+x}) and exports==sorted({x.split()[-1] for x in oldsymbols if len(x.split())>=3 and x.split()[-2] in ('T','D','B','R')}),'Owner ABI changed')
 validator=O/'validate-elf';subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(S/'test/native_apps/stubs'),'-I'+str(S/'lib/elf_loader/include'),str(S/'lib/elf_loader/src/esp_elf_validate.c'),str(S/'test/native_apps/validate_test.c'),'-o',str(validator)],check=True);subprocess.run([str(validator),str(O/'default.elf')],check=True)
 manifest['version']=OWNER_VERSION;(O/'default.json').write_text(json.dumps(manifest,indent=2)+'\n')
 for relative,row in overlay.items():require(sha(S/relative)==row['sha256'],'Overlay changed while building')
 clean(ROOT,revision);clean(S,a.system_commit)
 record=dict(schema='lists.x4-resident-owner.component.v1',device='x4',version=OWNER_VERSION,sha256=sha(O/'default.elf'),bytes=(O/'default.elf').stat().st_size,manifest_sha256=sha(O/'default.json'),compiler=compiler,compiler_path=cc,compiler_command=cmd,defines=[x for x in cmd if x.startswith('-D')],added_defines=[],selected_system_commit=profile['selected_system_commit'],selected_system_tree=profile['selected_system_tree'],system_overlay_commit=a.system_commit,approved_source_overlays=overlay,sources={'selected-system':profile['selected_system_commit'],'system-apps':a.system_commit,'selected-product':profile['selected_product_commit']},source_roots={k:str(v) for k,v in staged.items()},product_recipe=revision,build_recipe_sha256=sha(__file__),target_dependencies=actual_deps,predecessor_actual_dependencies=predecessor_deps,historical_trace_difference={'actual_compile_uses':'toolchain:lib/gcc/xtensa-esp32s3-elf/8.4.0/include/stdint-gcc.h','historical_inventory_only':['toolchain:xtensa-esp32s3-elf/sys-include/stdint.h','toolchain:xtensa-esp32s3-elf/sys-include/sys/_intsup.h'],'selected_elf_reproduction_exact':True},predecessor=results['predecessor'],repeat_exact_identity=True,original_dependency_spellings=213,original_unique_dependencies=len(profile['input_hashes']),fonts_and_all_other_inputs_preserved=True,original_flags_and_boot_wake_fixes_preserved=True,authority_unchanged=True,imports=imports,exports=exports,native_runtime_firmware_changed=False,hardware_verified=False)
 (O/'owner-build-record.json').write_text(json.dumps(record,indent=2)+'\n');print('X4 resident owner',record['bytes'],record['sha256']);return record
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['system','baseline','predecessor-evidence','selected-system','selected-product','relocation-tools','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--system-commit',required=True);build(p.parse_args())
