#!/usr/bin/env python3
"""Overlay audited OBD and BLE serial on a pinned, complete X4 union.

No native firmware changes. Retain all unrelated store/SD bytes, and retain the
old immutable provider image. Only OBD's canonical app image/manifest are replaced.
"""
import argparse,copy,hashlib,json,os,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools
from compose_shared_settings_090 import audit_selected_images
from compose_timecard_shared_input import streamed_image_digest
from boot_order_spiffs import build as ordered_build
ROOT=Path(__file__).resolve().parents[2]
ZIP='X4-0.1.102-Combined-Changed-SD.zip'
CHANGED={'obd_dashboard.json','ble-serial/driver.elf','ble-serial/manifest.json','boot.json','cohort.json'}
SD_CHANGED={'Apps/obd-dashboard/obd_dashboard.elf','Apps/obd-dashboard/manifest.json'}

def payload(old,old_sd,data,revision):
 require(set(data)=={'obd_dashboard.elf','obd_dashboard.json','ble-serial/driver.elf','ble-serial/manifest.json'},'Unexpected component members')
 require(json.loads(old['obd_dashboard.json'])['version']=='0.2.1','Wrong OBD predecessor')
 require(json.loads(old['ble-serial/manifest.json'])['version']=='0.1.0','Wrong BLE serial predecessor')
 require(old['obd_dashboard.json']==old_sd['Apps/obd-dashboard/manifest.json'],'OBD predecessor manifests disagree')
 require(json.loads(data['obd_dashboard.json'])==dict(json.loads(old['obd_dashboard.json']),version='0.2.2'),'OBD authority or features changed')
 require(json.loads(data['ble-serial/manifest.json'])==dict(json.loads(old['ble-serial/manifest.json']),version='0.1.1'),'BLE serial authority changed')
 new=dict(old);sd=dict(old_sd)
 for name in ('obd_dashboard.json','ble-serial/driver.elf','ble-serial/manifest.json'):new[name]=data[name]
 sd['Apps/obd-dashboard/manifest.json']=data['obd_dashboard.json'];sd['Apps/obd-dashboard/obd_dashboard.elf']=data['obd_dashboard.elf']
 boot=json.loads(old['boot.json']);original=copy.deepcopy(boot)
 rows=[r for r in boot['drivers'] if r['manifest']=='ble-serial/manifest.json'];require(len(rows)==1,'Missing unique BLE serial policy')
 row=rows[0];before=copy.deepcopy(row['image_source']);require(before=={'internal_fallback':True,'volume_instance':9,'path':'Drivers/ble-serial/image-'+sha(old['ble-serial/driver.elf'])+'.elf'},'Wrong provider selection')
 require(old_sd[before['path']]==old['ble-serial/driver.elf'],'Provider fallback differs')
 path='Drivers/ble-serial/image-'+sha(data['ble-serial/driver.elf'])+'.elf';require(path not in sd,'Provider image already exists')
 sd[path]=data['ble-serial/driver.elf'];row['image_source']['path']=path;new['boot.json']=encoded(boot)
 row['image_source']=before;require(boot==original,'Boot authority changed')
 cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.102','Wrong cohort version');cohort['source_revision']=revision;new['cohort.json']=encoded(cohort)
 require(set(new)==set(old) and {n for n in old if old[n]!=new[n]}==CHANGED,'Unexpected store delta')
 require(set(sd)==set(old_sd)|{path} and {n for n in old_sd if old_sd[n]!=sd[n]}==SD_CHANGED,'Unexpected SD delta')
 return new,sd,{path}

def write_shared(root,items,baseline):
 """Hard-link byte-identical immutable inputs to avoid duplicate sparse trees."""
 for name,data in items.items():
  dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);prior=baseline/name
  if prior.is_file() and prior.read_bytes()==data:os.link(prior,dest)
  else:dest.write_bytes(data)

def compose(a):
 require(not a.output.exists(),'Use a fresh output directory')
 revision=git(ROOT,'rev-parse','HEAD');clean_source(ROOT,revision,'Product')
 lock=json.loads((ROOT/'minimal/obd-readiness-inputs.json').read_bytes())
 raw=(a.baseline/'receipts/evening-composition.json').read_bytes();base=json.loads(raw)
 require(sha(raw)==lock['baseline_receipt_sha256'] and base['product_source']==lock['baseline_product_source'] and base['full_image_sha256']==lock['baseline_full_image_sha256'],'Wrong frozen predecessor')
 clean_source(a.runtime,base['runtime_commit'],'Runtime');require(git(a.runtime,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Runtime tree differs')
 old,old_sd,parts=[read_tree(a.baseline/n) for n in ('store','SD','components')]
 require(inventory(old)==base['store'] and inventory(old_sd)==base['sd'],'Baseline inventory differs')
 require(streamed_image_digest(parts,base['components'])==base['full_image_sha256'],'Baseline sparse image differs')
 require(sha(old_sd['Apps/obd-dashboard/obd_dashboard.elf'])==lock['prior_obd_sha256'] and sha(old['ble-serial/driver.elf'])==lock['prior_serial_sha256'],'Wrong selected predecessors')
 app=json.loads((a.obd_build/'build.json').read_bytes());serial=json.loads((a.serial_build/'build.json').read_bytes())
 require(app['version']=='0.2.2' and all(not v['dirty'] for v in app['sources'].values()),'OBD source is dirty or wrong version')
 require({k:v['commit'] for k,v in app['sources'].items()}==lock['obd_sources'],'Unexpected OBD sources')
 require(serial['version']=='0.1.1' and not serial['source_dirty'] and serial['source_revision']==lock['serial_source'],'Unexpected BLE serial source')
 require(not app['hardware_tested'] and not serial['hardware_tested'],'Unexpected hardware assertion')
 data={n:(a.obd_build/n).read_bytes() for n in ('obd_dashboard.elf','obd_dashboard.json')}
 for n in ('driver.elf','manifest.json'):data['ble-serial/'+n]=(a.serial_build/n).read_bytes()
 require(sha(data['obd_dashboard.elf'])==app['sha256']==lock['obd_sha256'] and len(data['obd_dashboard.elf'])==app['bytes'],'OBD ELF custody differs')
 require(sha(data['ble-serial/driver.elf'])==serial['sha256']==lock['serial_sha256'] and len(data['ble-serial/driver.elf'])==serial['bytes'],'Provider ELF custody differs')
 new,sd,additions=payload(old,old_sd,data,revision)
 pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime);image,packing=ordered_build(new,pack)
 require(ordered_build(dict(reversed(list(new.items()))),pack)==(image,packing),'Nondeterministic packing')
 prior=json.loads((a.baseline/'receipts/packing.json').read_bytes())
 for k in ('ordered_paths','order_recipe_sha256','generator_sha256','config','metadata','file_count','image_bytes'):require(packing[k]==prior[k],'Startup packing changed: '+k)
 require(packing['empty_blocks']>=2,'SPIFFS reserve violated');require(decode(image,0x510000)==new,'Independent store readback differs')
 firmware=parts['firmware.bin'];state=bank(firmware,image,True);row=parse(state[:96],True)
 require(row[3]==len(firmware) and row[6]==hashlib.sha256(firmware).digest() and row[7]==hashlib.sha256(image).digest(),'Bank digest differs')
 with tempfile.TemporaryDirectory(prefix='x4-obd-readiness-') as temp:
  t=Path(temp);write_shared(t/'store',new,a.baseline/'store');write_shared(t/'SD',sd,a.baseline/'SD');selected=audit_selected_images(json.loads(new['boot.json']),t/'store',t/'SD')
 before={r['manifest']:r for r in base['selected_sd_images']};after={r['manifest']:r for r in selected}
 require(len(selected)==48 and set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'obd_dashboard.json','ble-serial/manifest.json'},'Unexpected selected image delta')
 overlay_paths=set(base['sd_overlay']['files'])|SD_CHANGED|additions;overlay={n:sd[n] for n in sorted(overlay_paths)}
 parts.update({'bootfs.bin':image,'bank_state.bin':state});full_sha=streamed_image_digest(parts,base['components'])
 receipt=copy.deepcopy(base)
 receipt.update(schema='x4.obd-readiness-composition.v1',product_source=revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=base['product_source'],baseline_full_image_sha256=base['full_image_sha256'],baseline_receipt_sha256=sha(raw),recipe_sha256=sha(Path(__file__).read_bytes()),store=inventory(new),sd=inventory(sd),selected_sd_images=selected,changed_store_paths=sorted(CHANGED),changed_sd_paths=sorted(SD_CHANGED),added_sd_files=sorted(additions),original_sd_files_preserved=len(old_sd)-len(SD_CHANGED),boot_authority_unchanged=True,boot_authority_delta=[],boot_image_selection_changed=['ble-serial/manifest.json'],obd_build=app,serial_build=serial,obd_0_2_1_unchanged=False,components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),full_image_bytes=0x1000000,full_image_sha256=full_sha,current_component_versions=dict(base['current_component_versions'],obd_dashboard='0.2.2',ble_serial='0.1.1'),native_rebuilt=False,native_unchanged=True,independent_full_image_verified=True,hardware_tested=False,physical_adapter_verified=False,target_instructions_executed=False,full_image_materialized=False,delivered=False,delivery_hold_until_utc='2026-10-12T23:30:00Z',unpublished_sd_settings_consumed=False)
 receipt['excluded']=[x for x in receipt.get('excluded',[]) if x!='unqualified OBD audit changes']
 receipt['source_lock']['excluded']=[x for x in receipt['source_lock'].get('excluded',[]) if x!='unqualified OBD audit changes']
 receipt['component_sources']['obd-dashboard']=dict(repository='michaelrolphone-cmyk/RiscRTE-Utilities',commit=lock['obd_sources']['utilities'],version='0.2.2',build_record_sha256=sha((a.obd_build/'build.json').read_bytes()))
 receipt['component_sources']['ble-serial']=dict(repository='michaelrolphone-cmyk/RiscRTE-Drivers',commit=lock['serial_source'],version='0.1.1',build_record_sha256=sha((a.serial_build/'build.json').read_bytes()))
 a.output.mkdir(parents=True)
 for n,items in [('store',new),('SD',sd),('components',parts)]:write_shared(a.output/n,items,a.baseline/n)
 with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,data in overlay.items():
   entry=zipfile.ZipInfo(n,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
 with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'SD ZIP readback differs')
 receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96',immediate_delta_from='0.1.102 Contexts lifecycle union',immediate_delta_paths=sorted(SD_CHANGED|additions))
 write_files(a.output/'receipts',{'evening-composition.json':encoded(receipt),'packing.json':encoded(packing),'obd-build.json':encoded(app),'serial-build.json':encoded(serial),'obd-readiness-inputs.json':encoded(lock)})
 require(read_tree(a.output/'store')==new and read_tree(a.output/'SD')==sd,'Written output differs');clean_source(ROOT,revision,'Product')
 print(json.dumps(dict(sha256=full_sha,sd_overlay_files=len(overlay),free_blocks=packing['empty_blocks'],native_unchanged=True,hardware_tested=False)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('baseline','obd-build','serial-build','runtime','tools','output'):p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
 compose(p.parse_args())
