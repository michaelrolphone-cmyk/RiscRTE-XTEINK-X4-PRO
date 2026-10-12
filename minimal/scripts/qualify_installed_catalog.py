#!/usr/bin/env python3
"""Strict target ELF/import and native store metadata admission; no execution."""
import argparse,json,subprocess,sys,shutil,copy
from pathlib import Path
from package_reader_bin_overlay import native_witness,compile_admission,imports,sha
p=argparse.ArgumentParser(description=__doc__)
for name in ('runtime','tools','native-bin','store','output'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--provider-capacity',type=int,choices=[29,32,40],default=29)
p.add_argument('--shared-files',action='store_true')
p.add_argument('--sd',type=Path,help='Also admit every actually selected SD image')
p.add_argument('--composition-receipt',type=Path,help='Exact .90, Files-only .92 or fast-boot .94 receipt paired with --sd')
p.add_argument('--native-elf',type=Path,required=True,help='Exact ELF paired with native-bin, used to derive native USB PHY registration')
a=p.parse_args()
if bool(a.sd)!=bool(a.composition_receipt):p.error('--sd and --composition-receipt must be supplied together')
a.runtime=a.runtime.resolve();a.tools=a.tools.resolve();a.native_bin=a.native_bin.resolve();a.store=a.store.resolve();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.runtime.resolve()/'scripts'));sys.path.insert(0,str(a.tools.resolve()/'scripts'))
if (a.native_elf.parent/'firmware.bin').read_bytes()!=a.native_bin.read_bytes():raise ValueError('native ELF sibling firmware differs from supplied native-bin')
from elftools.elf.elffile import ELFFile
with a.native_elf.open('rb') as native_file:
 elf=ELFFile(native_file);symbols=elf.get_section_by_name('.symtab')
 rows=symbols.get_symbol_by_name('risc_usb_phy_resource_enabled') or []
 native_usb_phy=False
 for row in rows:
  if row['st_shndx']!='SHN_UNDEF':
   section=elf.get_section(row['st_shndx']);offset=row['st_value']-section['sh_addr']
   if section.data()[offset:offset+4] != b'\x01\x00\x00\x00':raise ValueError('Invalid native USB PHY selector')
   native_usb_phy=True
print('Linked native USB PHY registration:',native_usb_phy,flush=True)
exports,witness=native_witness(a.runtime,a.native_bin.read_bytes())
info=compile_admission(a.runtime,a.tools,a.output/'ubsan',exports,True,'undefined',installed_catalog=True,shared_files=a.shared_files,provider_capacity=a.provider_capacity,native_usb_phy=native_usb_phy)
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
info.update(native_usb_phy=native_usb_phy,native_elf_sha256=sha(a.native_elf.read_bytes()),native=witness,modules=modules,admission=admission,rejected_namespace_changes=rejections,hardware_tested=False,scope='Actual native ELF role/import admission and Runtime metadata; provider/application execution is not tested here.')
if a.sd:
 from compose_shared_settings_090 import audit_selected_images,git
 composition=json.loads(a.composition_receipt.read_text())
 if composition['runtime_commit']!=git(a.runtime,'rev-parse','HEAD') or git(a.runtime,'status','--porcelain'):
  raise ValueError('Selected SD admission Runtime differs from clean composition source')
 if composition['product_version'] not in ('0.1.90','0.1.92','0.1.94','0.1.95','0.1.96') or composition['shared_settings_enabled'] is not False:
  raise ValueError('Selected SD admission requires qualified opt-out .90/.92/.94/.95/.96 composition')
 if composition['product_version']=='0.1.92':
  from compose_files_092 import ALLOWED,VERSION
  from compose_shared_settings_090 import tree
  if (composition['changed_store_paths']!=sorted(ALLOWED) or composition['sd_overlay_required'] is not False or
      composition['original_sd_files_preserved']!=81 or composition['added_sd_files']!=[] or
      composition['native_unchanged'] is not True or composition['boot_authority_unchanged'] is not True or
      composition['firmware_sha256']!=witness['firmware_sha256'] or
      composition['store']!=tree(a.store) or composition['sd']!=tree(a.sd.resolve()) or
      json.loads((a.store/'cohort.json').read_text())['version']!=VERSION):
   raise ValueError('Files-only .92 composition preservation evidence differs')
 if composition['product_version']=='0.1.96':
  from sd_resident_lifecycle import validate
  from compose_desk_wake_093 import read_tree
  from compose_shared_settings_090 import tree
  rows=validate(read_tree(a.store),read_tree(a.sd.resolve()))
  if (composition['sd_lifecycle']!=rows or composition['sd_overlay_required'] is not True or
      composition['changed_store_paths']!=sorted({'cohort.json'}|{r['manifest'] for r in rows}) or
      composition['changed_sd_paths']!=sorted(r['sd_manifest'] for r in rows) or
      composition['original_sd_files_preserved']!=68 or composition['added_sd_files']!=[] or
      composition['all_sd_executables_preserved'] is not True or composition['native_unchanged'] is not True or
      composition['home_rebuilt'] is not False or composition['boot_authority_unchanged'] is not True or
      composition['firmware_sha256']!=witness['firmware_sha256'] or
      composition['firmware_elf_sha256']!=sha(a.native_elf.read_bytes()) or
      composition['store']!=tree(a.store) or composition['sd']!=tree(a.sd.resolve()) or
      json.loads((a.store/'cohort.json').read_text())['version']!='0.1.96'):
   raise ValueError('SD lifecycle .96 composition preservation evidence differs')
 if composition['product_version']=='0.1.95':
  from compose_boot_order_095 import ALLOWED,VERSION
  from compose_shared_settings_090 import tree
  if (composition['changed_store_paths']!=sorted(ALLOWED) or composition['sd_overlay_required'] is not False or
      composition['original_sd_files_preserved']!=81 or composition['added_sd_files']!=[] or
      composition['native_unchanged'] is not True or composition['home_rebuilt'] is not False or
      composition['boot_authority_unchanged'] is not True or
      composition['firmware_sha256']!=witness['firmware_sha256'] or
      composition['firmware_elf_sha256']!=sha(a.native_elf.read_bytes()) or
      composition['store']!=tree(a.store) or composition['sd']!=tree(a.sd.resolve()) or
      json.loads((a.store/'cohort.json').read_text())['version']!=VERSION):
   raise ValueError('Boot-order .95 composition preservation evidence differs')
 if composition['product_version']=='0.1.94':
  from compose_fast_boot_094 import ALLOWED,VERSION
  from compose_shared_settings_090 import tree
  if (composition['changed_store_paths']!=sorted(ALLOWED) or composition['sd_overlay_required'] is not False or
      composition['original_sd_files_preserved']!=81 or composition['added_sd_files']!=[] or
      composition['native_rebuilt'] is not True or composition['boot_authority_unchanged'] is not True or
      composition['firmware_sha256']!=witness['firmware_sha256'] or
      composition['firmware_elf_sha256']!=sha(a.native_elf.read_bytes()) or
      composition['store']!=tree(a.store) or composition['sd']!=tree(a.sd.resolve()) or
      json.loads((a.store/'cohort.json').read_text())['version']!=VERSION):
   raise ValueError('Fast-boot .94 composition preservation evidence differs')
 selected=audit_selected_images(json.loads((a.store/'boot.json').read_text()),a.store,a.sd.resolve())
 if selected!=composition['selected_sd_images'] or len(selected)!=46:
  raise ValueError('Selected SD source/hash inventory differs from composition')
 for row in selected:
  path=a.sd.resolve()/row['path']
  if set(imports(path.read_bytes()))-set(exports):raise ValueError('Unresolved selected SD imports: '+row['path'])
  subprocess.run([str(a.output/'ubsan/strict'),row['role'],str(path)],check=True)
  row['strict_admission_passed']=True
 sd_info=dict(runtime_commit=composition['runtime_commit'],native_firmware_sha256=witness['firmware_sha256'],
              strict_validator_sha256=sha((a.output/'ubsan/strict').read_bytes()),selected_images=selected,hardware_tested=False)
 (a.output/'selected-sd-admission.json').write_text(json.dumps(sd_info,indent=2)+'\n')
 info['selected_sd_admission_sha256']=sha((a.output/'selected-sd-admission.json').read_bytes())
 info['selected_sd_images']=len(selected)
(a.output/'evidence.json').write_text(json.dumps(info,indent=2)+'\n')
