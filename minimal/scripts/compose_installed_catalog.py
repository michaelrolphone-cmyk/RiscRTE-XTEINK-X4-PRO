#!/usr/bin/env python3
"""Compose a development boot store selecting cached installed-app discovery.

No image generation, publication, migration, flash, or release promotion. Existing
app grants remain intact; new SD identities are admitted under the envelope.
"""
import argparse, hashlib, json, shutil
from pathlib import Path

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('base-store','springboard','sd','catalog','output'):p.add_argument('--'+key,type=Path,required=True)
 a=p.parse_args();base=a.base_store.resolve();out=a.output.resolve()
 if out.exists():raise ValueError('Output must be new')
 boot=json.loads((base/'boot.json').read_text())
 if len(boot['drivers'])>=29:raise ValueError('No provider slot remains')
 if any('installation'==key for key in boot):raise ValueError('Existing installation policy needs explicit review')
 sd=next(x for x in boot['drivers'] if x['manifest']=='sd/manifest.json')
 if sd.get('instance_id')!=9:raise ValueError('Expected exact X4 SD binding')
 spring=json.loads((a.springboard/'springboard.json').read_text())
 needs={(x['capability'],x['api'])for x in spring['requires']}
 if ('software.installed-apps',1) not in needs or ('storage.volume',1) not in needs:raise ValueError('Springboard lacks installed catalog')
 selected=next(x for x in boot['app_capabilities'] if x['manifest']=='springboard.json')
 for cap,instance in (('software.installed-apps',0),('storage.volume',9)):
  selected['grants'].append(dict(capability=cap,api=1,instance_id=instance))
 # Exact owner-selected services; declarations from SD cannot redirect hardware,
 # acquire raw native authority, or select another app's settings namespace.
 envelope=[]
 for cap,api,instance in [('display.output',1,3),('input.touch.raw',1,4),('input.navigation',1,6),
  ('board.battery',1,7),('alarm.service',2,0),('storage.volume',1,9),('file.open',1,0),
  ('runtime.realtime',1,0),('storage.key-value',1,0),('storage.app-data',1,0)]:
  envelope.append(dict(capability=cap,api=api,instance_id=instance))
 boot['installation']=dict(volume_instance=9,grants=envelope,namespace_range=dict(first=3000,count=128))
 boot['drivers'].append(dict(manifest='installed-apps/manifest.json',app_data=[dict(name='installed.apps',namespace=2000,access='read-write')]))
 sd_manifest=json.loads((a.sd/'manifest.json').read_text())
 if not any(x['capability']=='platform.storage-worker'for x in sd_manifest['requires']):raise ValueError('Async SD provider required')
 catalog_manifest=json.loads((a.catalog/'manifest.json').read_text())
 if catalog_manifest['version']!='0.3.1':raise ValueError('Durable namespace catalog provider required')
 shutil.copytree(base,out)
 replacements={'springboard.elf':a.springboard/'springboard.elf','springboard.json':a.springboard/'springboard.json',
  'sd/driver.elf':a.sd/'driver.elf','sd/manifest.json':a.sd/'manifest.json',
  'installed-apps/driver.elf':a.catalog/'driver.elf','installed-apps/manifest.json':a.catalog/'manifest.json'}
 for name,source in replacements.items():
  target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 (out/'boot.json').write_text(json.dumps(boot,indent=2)+'\n')
 receipt=dict(status='development-store-not-a-release',base_boot_sha256=digest(base/'boot.json'),boot_sha256=digest(out/'boot.json'),
  apps=len(boot['app_capabilities']),drivers=len(boot['drivers']),volume_instance=9,cache_namespace=2000,namespace_range=boot['installation']['namespace_range'],
  replaced={name:dict(sha256=digest(out/name),bytes=(out/name).stat().st_size)for name in replacements},
  remaining=['Strict complete store/native admission','Preserving migration of legacy explicit SD entries and their shared/private settings','App Store installed-catalog UI and SD installation transactions','On-device dependency provisioning','Hardware qualification'],
  hardware_tested=False,flashable=False)
 (out.parent/(out.name+'-composition.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
