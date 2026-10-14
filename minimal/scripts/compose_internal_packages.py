#!/usr/bin/env python3
"""Compose a separate development store, preserving the selected boot baseline.

Requires newly built Runtime with RISC_NATIVE_PACKAGE_VOLUME=1. Never edits the
input store, generates firmware, or changes installed app grants/registrations.
"""
import argparse,hashlib,json,shutil
from pathlib import Path

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def compose(base,expected,sd,catalog,internal,out):
 if out.exists():raise ValueError('Output must be new')
 if digest(base/'boot.json')!=expected:raise ValueError('Selected boot baseline hash mismatch')
 boot=json.loads((base/'boot.json').read_text());before=json.loads(json.dumps(boot))
 policy=boot.get('installation',{})
 if policy.get('volume_instance')!=9 or 'internal_volume_instance' in policy:raise ValueError('Expected selected SD catalog policy')
 if len(boot['drivers'])>=40:raise ValueError('No provider slot remains')
 expected_packages=[(sd,'x4pro-sd','0.2.24','sd'),(catalog,'installed-apps','0.10.0','installed-apps'),(internal,'internal-packages','0.1.0','internal-packages')]
 for source,identity,version,name in expected_packages:
  m=json.loads((source/'manifest.json').read_text())
  if (m.get('id'),m.get('version'),m.get('file_name'))!=(identity,version,'driver.elf'):raise ValueError('Wrong selected package: '+name)
  if not (source/'driver.elf').read_bytes().startswith(b'\x7fELF'):raise ValueError('Missing ELF: '+name)
  if name!='sd' and not any(x.get('capability')=='platform.package-volume' and x.get('api')==1 for x in m['requires']):raise ValueError('Internal capability not selected')
  if name=='internal-packages':
   boot['drivers'].append({'manifest':name+'/manifest.json'})
  else:
   matches=[x for x in boot['drivers'] if x['manifest']==name+'/manifest.json']
   if len(matches)!=1:raise ValueError('Ambiguous original provider: '+name)
   if 'image_source' in matches[0]:
    image=matches[0]['image_source']
    if image.get('volume_instance')!=9 or image.get('internal_fallback') is not True:raise ValueError('Unexpected source custody')
    image['path']='Drivers/'+identity+'/image-'+digest(source/'driver.elf')+'.elf'
 policy['internal_volume_instance']=0
 assert boot['app_capabilities']==before['app_capabilities']
 assert {k:v for k,v in policy.items() if k!='internal_volume_instance'}==before['installation']
 shutil.copytree(base,out)
 for source,identity,version,name in expected_packages:
  dest=out/name;dest.mkdir(exist_ok=True)
  for file in ('driver.elf','manifest.json'):shutil.copyfile(source/file,dest/file)
 (out/'boot.json').write_text(json.dumps(boot,indent=2)+'\n')
 receipt={'status':'development-store-only','base_boot_sha256':expected,'boot_sha256':digest(out/'boot.json'),'required_native_flags':['RISC_NATIVE_PACKAGE_VOLUME=1','RISC_NATIVE_APP_DATA_MOUNT=1','RISC_PAIRED_APP_DATA'],'apps_preserved':len(boot['app_capabilities']),'drivers':len(boot['drivers']),'hardware_tested':False,'packages':{identity:digest(source/'driver.elf') for source,identity,version,name in expected_packages}}
 (out/'internal-packages-composition.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('base-store','sd','catalog','internal','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--base-boot-sha256',required=True);a=p.parse_args()
 print(json.dumps(compose(a.base_store,a.base_boot_sha256,a.sd,a.catalog,a.internal,a.output),indent=2))
