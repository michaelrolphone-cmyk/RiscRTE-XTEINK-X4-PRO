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
 for key in ('base-store','springboard','app-store','sd','catalog','output'):p.add_argument('--'+key,type=Path,required=True)
 p.add_argument("--home",type=Path,help="Home profile with first-frame catalog hydration")
 p.add_argument("--migrate-legacy",action="store_true",help="Select dormant legacy SD authority and a matching internal-only Springboard catalog")
 p.add_argument("--provider-capacity",type=int,choices=[29,32],default=29)
 a=p.parse_args();base=a.base_store.resolve();out=a.output.resolve()
 if out.exists():raise ValueError('Output must be new')
 boot=json.loads((base/'boot.json').read_text())
 if len(boot['drivers'])>=a.provider_capacity:raise ValueError('No provider slot remains')
 if any('installation'==key for key in boot):raise ValueError('Existing installation policy needs explicit review')
 sd=next(x for x in boot['drivers'] if x['manifest']=='sd/manifest.json')
 if sd.get('instance_id')!=9:raise ValueError('Expected exact X4 SD binding')
 spring=json.loads((a.springboard/'springboard.json').read_text())
 needs={(x['capability'],x['api'])for x in spring['requires']}
 if ('software.installed-apps',1) not in needs or ('storage.volume',1) not in needs:raise ValueError('Springboard lacks installed catalog')
 selected=next(x for x in boot['app_capabilities'] if x['manifest']=='springboard.json')
 for cap,instance in (('software.installed-apps',0),('storage.volume',9)):
  selected['grants'].append(dict(capability=cap,api=1,instance_id=instance))
 app_store=json.loads((a.app_store/'app_store.json').read_text())
 old_store=json.loads((base/'app_store.json').read_text())
 old_needs={(x['capability'],x['api'])for x in old_store['requires']}
 new_needs={(x['capability'],x['api'])for x in app_store['requires']}
 if app_store['version']!='1.4.0' or new_needs!=old_needs|{('software.installed-apps',1),('storage.volume',1)}:raise ValueError('App Store capability/version mismatch')
 app_store_policy=next(x for x in boot['app_capabilities'] if x['manifest']=='app_store.json')
 for cap,instance in (('software.installed-apps',0),('storage.volume',9)):
  app_store_policy['grants'].append(dict(capability=cap,api=1,instance_id=instance))
 # Exact owner-selected services; declarations from SD cannot redirect hardware,
 # acquire raw native authority, or select another app's settings namespace.
 envelope=[]
 for cap,api,instance in [('display.output',1,3),('input.touch.raw',1,4),('input.navigation',1,6),
  ('board.battery',1,7),('alarm.service',2,0),('storage.volume',1,9),('file.open',1,0),
  ('runtime.realtime',1,0),('storage.key-value',1,0),('storage.app-data',1,0)]:
  envelope.append(dict(capability=cap,api=api,instance_id=instance))
 boot['installation']=dict(volume_instance=9,grants=envelope,namespace_range=dict(first=3000,count=128))
 if a.migrate_legacy and not a.home:raise ValueError('Legacy migration requires Home cache hydration for preserved shortcuts')
 if a.home:
  home=json.loads((a.home/'default.json').read_text());old_home=json.loads((base/'default.json').read_text())
  home_record=json.loads((a.home/'build-evidence.json').read_text())
  if home['version']!='0.4.9' or {(x['capability'],x['api'])for x in home['requires']}!={(x['capability'],x['api'])for x in old_home['requires']}|{('software.installed-apps',1)} or home_record.get('installed_catalog',{}).get('volume_instance')!=9:
   raise ValueError('Home must preserve all capabilities and hydrate the exact SD catalog')
  next(x for x in boot['app_capabilities'] if x['manifest']=='default.json')['grants'].append(dict(capability='software.installed-apps',api=1,instance_id=0))
 if a.migrate_legacy:
  record=json.loads((a.springboard/'springboard-build-record.json').read_text())
  expected=[]
  for policy in boot['app_capabilities']:
   if 'image_source' not in policy:continue
   manifest=json.loads((base/policy['manifest']).read_text());expected.append(manifest['file_name'])
   if policy['image_source']['volume_instance']!=9:raise ValueError('Unexpected legacy SD volume')
   policy['catalog_authority']=True
  if spring['version']!='1.8.1' or sorted(record['catalog'].get('sd_authority_files',[]))!=sorted(expected) or record['catalog'].get('authority_boot_sha256')!=digest(base/'boot.json'):
   raise ValueError('Springboard compiled list must exclude exact legacy SD source identities')

 boot['drivers'].append(dict(manifest='installed-apps/manifest.json',app_data=[dict(name='installed.apps',namespace=2000,access='read-write')]))
 sd_manifest=json.loads((a.sd/'manifest.json').read_text())
 if sd_manifest['version']!='0.2.20':raise ValueError('Async version-three SD provider required')
 if not any(x['capability']=='platform.storage-worker'for x in sd_manifest['requires']):raise ValueError('Async SD provider required')
 catalog_manifest=json.loads((a.catalog/'manifest.json').read_text())
 if catalog_manifest['version']!='0.4.0':raise ValueError('Durable namespace catalog provider required')
 shutil.copytree(base,out)
 replacements={'app_store.elf':a.app_store/'app_store.elf','app_store.json':a.app_store/'app_store.json','springboard.elf':a.springboard/'springboard.elf','springboard.json':a.springboard/'springboard.json',
  'sd/driver.elf':a.sd/'driver.elf','sd/manifest.json':a.sd/'manifest.json',
  'installed-apps/driver.elf':a.catalog/'driver.elf','installed-apps/manifest.json':a.catalog/'manifest.json'}
 if a.home:replacements.update({"default.elf":a.home/"default.elf","default.json":a.home/"default.json"})
 for name,source in replacements.items():
  target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 (out/'boot.json').write_text(json.dumps(boot,indent=2)+'\n')
 receipt=dict(status='development-store-not-a-release',base_boot_sha256=digest(base/'boot.json'),boot_sha256=digest(out/'boot.json'),
  apps=len(boot['app_capabilities']),drivers=len(boot['drivers']),volume_instance=9,cache_namespace=2000,namespace_range=boot['installation']['namespace_range'],
  replaced={name:dict(sha256=digest(out/name),bytes=(out/name).stat().st_size)for name in replacements},
  remaining=['Strict complete store/native admission']+([] if a.migrate_legacy else ['Select preserving migration of legacy SD authority'])+['On-device missing-provider dependency provisioning','Hardware qualification'],
  hardware_tested=False,flashable=False)
 (out.parent/(out.name+'-composition.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
