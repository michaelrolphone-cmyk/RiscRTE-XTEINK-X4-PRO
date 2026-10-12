#!/usr/bin/env python3
"""Add OBD to the exact qualified .97 cohort without replacing native/Home/Files code."""
import argparse,copy,hashlib,json,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools,BOOTFS,BANK_STATE
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build
from sd_resident_lifecycle import validate as validate_baseline_lifecycle
from package_resident_cohort import descriptor

ROOT=Path(__file__).resolve().parents[2]
BASE='e9332c3fe731ed63508e223bcd67cedf481462e4'
BASE_SHA='d18ad4726d6503b53a17c556cc1e8bc6a40769885c7c60c176b393707a499dd6'
BASE_RECEIPT='2fe8247a7d9bd45d3ffac80e20ed37de5dd74faea84566e0b14940b071a748ff'
VERSION='0.1.98';IMAGE='X4-0.1.98-OBD-FULL-INITIAL-ERASES-DATA.bin';ZIP='X4-0.1.98-OBD-SD-Overlay.zip'
APP_SHA='b2ca8861412e3b79fb6cad14516c574cc2f4479107eaa0bb35165a8059c27f20'
SCENE_SHA='25b12c8e807e1d57684badf8e1d9b3f4b188cd6896a88f4e82f2287e31fbbb6d'
DRIVER_SHA='cc5bf2a38bf655c1cb51cbdaf3eacbffff69b852adbfb57363ee366cc453ef1f'
ADDED={'ble-serial/driver.elf','ble-serial/manifest.json','obd_dashboard.json'}
CHANGED={'boot.json','cohort.json','ui-scene/driver.elf','ui-scene/manifest.json'}
MANIFEST_SHAS={'app': '9c1c64c6da5614f9096a07e8cd5181baa51aaf6fcfa3a854239b61c0bfe026c8', 'scene': '23d795967b2d05565393e027b2062c32d0b96ec6bd5bf284feb65e6ec9aa8ad0', 'driver': '0fa3d1cc175f9c561eb39eb5e5900559a4112d38cc700a5a031a77bc55f98535'}
APP_PATH='Apps/obd-dashboard/obd_dashboard.elf'
PRESERVED=((0,BOOTFS[0]),(BOOTFS[1],BANK_STATE[0]),(BANK_STATE[1],0x1000000))


def baseline(folder):
 raw=(folder/'receipts/mounted-files-composition.json').read_bytes();require(sha(raw)==BASE_RECEIPT,'Wrong qualified .97 receipt')
 receipt=json.loads(raw);full=(folder/'X4-0.1.97-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
 store,sd,parts=read_tree(folder/'store'),read_tree(folder/'SD'),read_tree(folder/'components')
 require(sha(full)==BASE_SHA and len(full)==0x1000000,'Wrong qualified .97 image')
 require(inventory(store)==receipt['store'] and len(store)==103,'Wrong .97 store')
 require(inventory(sd)==receipt['sd'] and len(sd)==81,'Wrong .97 SD source')
 require(set(parts)==set(receipt['components']),'Wrong .97 component set')
 for name,row in receipt['components'].items():
  data=parts[name];offset=row['offset']
  require(len(data)==row['bytes'] and sha(data)==row['sha256'] and full[offset:offset+len(data)]==data,'Wrong .97 component: '+name)
 validate_baseline_lifecycle(store,sd)
 return receipt,store,sd,parts,full


def payload(old,old_sd,app,scene,driver,revision):
 require(sha(app['obd_dashboard.elf'])==APP_SHA and sha(scene['driver.elf'])==SCENE_SHA and sha(driver['driver.elf'])==DRIVER_SHA,'Unqualified target build')
 require(sha(app['obd_dashboard.json'])==MANIFEST_SHAS['app'] and sha(scene['manifest.json'])==MANIFEST_SHAS['scene'] and sha(driver['manifest.json'])==MANIFEST_SHAS['driver'],'Unqualified component metadata')
 am=json.loads(app['obd_dashboard.json']);sm=json.loads(scene['manifest.json']);dm=json.loads(driver['manifest.json'])
 require(am['id']=='obd-dashboard' and am['version']=='0.2.1' and am['runtime_lifecycle']=='foreground' and am['requires']==[
  {'capability':'ui.scene','api':1},{'capability':'bluetooth.serial','api':1},{'capability':'storage.volume','api':1}], 'OBD identity/grants differ')
 require(am['file_name']=='obd_dashboard.elf' and am['entry']=='app_main' and am['architecture']=='xtensa-esp32s3','OBD image contract differs')
 descriptor(app['obd_dashboard.elf'],2,check_renderer=False)
 old_sm=json.loads(old['ui-scene/manifest.json'])
 require(sm['version']=='0.4.1' and {k:v for k,v in sm.items() if k!='version'}=={k:v for k,v in old_sm.items() if k!='version'},'Scene policy differs')
 require(dm['id']=='ble-serial' and dm['version']=='0.1.0' and dm['provides']==[{'capability':'bluetooth.serial','api':1}] and dm['requires']==[{'capability':'bluetooth.hci','api':1},{'capability':'platform.clock','api':1}], 'BLE serial policy differs')
 new=dict(old);sd=dict(old_sd);boot=json.loads(old['boot.json']);prior=copy.deepcopy(boot)
 require(len(boot['drivers'])==32 and len(boot['app_capabilities'])==26,'Unexpected .97 boot capacity')
 scene_path='Drivers/scene-host/image-'+SCENE_SHA+'.elf';driver_path='Drivers/ble-serial/image-'+DRIVER_SHA+'.elf'
 row=next(r for r in boot['drivers'] if r['manifest']=='ui-scene/manifest.json');old_scene_path=row['image_source']['path'];row['image_source']['path']=scene_path
 boot['drivers'].append({'manifest':'ble-serial/manifest.json','image_source':{'volume_instance':9,'path':driver_path,'internal_fallback':True}})
 boot['app_capabilities'].append({'manifest':'obd_dashboard.json','image_source':{'volume_instance':9,'path':APP_PATH},'catalog_authority':True,'grants':[
  {'capability':'ui.scene','api':1,'instance_id':0},{'capability':'bluetooth.serial','api':1,'instance_id':0},{'capability':'storage.volume','api':1,'instance_id':9}]})
 boot['resident_shell']['foreground'].append('obd_dashboard.elf')
 restored=copy.deepcopy(boot);restored['drivers'].pop();restored['app_capabilities'].pop();restored['resident_shell']['foreground'].pop()
 next(r for r in restored['drivers'] if r['manifest']=='ui-scene/manifest.json')['image_source']['path']=old_scene_path
 require(restored==prior,'Unrelated boot policy changed')
 new.update({'boot.json':encoded(boot),'ui-scene/driver.elf':scene['driver.elf'],'ui-scene/manifest.json':scene['manifest.json'],
  'ble-serial/driver.elf':driver['driver.elf'],'ble-serial/manifest.json':driver['manifest.json'],'obd_dashboard.json':app['obd_dashboard.json']})
 cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.97' and cohort['source_revision']==BASE and cohort['runtime_version']=='0.2.24','Wrong .97 cohort')
 cohort.update(version=VERSION,source_revision=revision);new['cohort.json']=encoded(cohort)
 sd.update({scene_path:scene['driver.elf'],driver_path:driver['driver.elf'],APP_PATH:app['obd_dashboard.elf'],'Apps/obd-dashboard/manifest.json':app['obd_dashboard.json']})
 require(set(new)-set(old)==ADDED and not set(old)-set(new) and {p for p in old if old[p]!=new[p]}==CHANGED,'Unexpected internal file changes')
 require(all(sd[p]==v for p,v in old_sd.items()) and set(sd)-set(old_sd)=={scene_path,driver_path,APP_PATH,'Apps/obd-dashboard/manifest.json'},'Unrelated SD change')
 # Remove only the added catalog record to reuse the exact .96 qualification.
 original_view=dict(new);keep=copy.deepcopy(boot);keep['app_capabilities'].pop();keep['resident_shell']['foreground'].pop();original_view['boot.json']=encoded(keep)
 require(validate_baseline_lifecycle(original_view,sd)==validate_baseline_lifecycle(old,old_sd),'Existing SD lifecycles changed')
 return new,sd


def verify_image(result,full,old,new,firmware,decode,parse):
 require(len(result)==len(full)==0x1000000,'Wrong complete image length')
 require(all(result[lo:hi]==full[lo:hi] for lo,hi in PRESERVED),'Unrelated native/data partition changed')
 require(decode(full[slice(*BOOTFS)],0x510000)==old,'Baseline flash decode differs')
 require(decode(result[slice(*BOOTFS)],0x510000)==new,'Final flash decode differs')
 state=result[slice(*BANK_STATE)];pair=parse(state[:96],True)
 require(pair[2]==0 and pair[3]==len(firmware) and pair[6]==hashlib.sha256(firmware).digest() and pair[7]==hashlib.sha256(result[slice(*BOOTFS)]).digest() and state[96:]==b'\xff'*(8192-96),'Bank authentication/initial state differs')


def compose(a):
 require(not a.output.exists(),'Output must be new');clean_source(ROOT,a.product_revision,'Product')
 require(git(ROOT,'merge-base',BASE,a.product_revision)==BASE,'Product must descend from .97')
 base,old,old_sd,parts,full=baseline(a.baseline);clean_source(a.runtime_source,base['runtime_commit'],'Runtime')
 require(git(a.runtime_source,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Wrong runtime tree')
 app,scene,driver=read_tree(a.app),read_tree(a.scene),read_tree(a.driver)
 sources=json.loads((ROOT/'minimal/obd-098-components.json').read_text())
 app_build=json.loads(app['build.json']);scene_build=json.loads(scene['build.json']);driver_build=json.loads(driver['build.json'])
 require(app_build['sha256']==APP_SHA and app_build['version']=='0.2.1' and scene_build['sha256']==SCENE_SHA and scene_build['version']=='0.4.1' and driver_build['sha256']==DRIVER_SHA,'Component build identity differs')
 for name in ('utilities','runtime','system','drivers'):
  require(app_build['sources'][name]=={'commit':sources[name]['commit'],'dirty':False},'Unqualified app dependency source: '+name)
 require(driver_build['source_revision']==sources['drivers']['commit'] and driver_build['source_dirty'] is False,'Unqualified serial source')
 new,sd=payload(old,old_sd,app,scene,driver,a.product_revision)
 pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime_source)
 require(decode(full[slice(*BOOTFS)],0x510000)==old,'Baseline flash decode differs')
 image,packing=ordered_build(new,pack);require(ordered_build(new,pack)[0]==image,'Nondeterministic packing')
 state=bank(parts['firmware.bin'],image,True);result=bytearray(full);result[slice(*BOOTFS)]=image;result[slice(*BANK_STATE)]=state
 verify_image(bytes(result),full,old,new,parts['firmware.bin'],decode,parse)
 with tempfile.TemporaryDirectory(prefix='x4-obd-selected-') as tmp:
  root=Path(tmp);write_files(root/'store',new);write_files(root/'SD',sd)
  selected=audit_selected_images(json.loads(new['boot.json']),root/'store',root/'SD');require(len(selected)==48,'Wrong selected SD count')
 overlay={p:v for p,v in sd.items() if p not in old_sd};parts=dict(parts,**{'bootfs.bin':image,'bank_state.bin':state})
 receipt=copy.deepcopy(base);receipt.update(product_version=VERSION,product_source=a.product_revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,
  baseline_full_image_sha256=BASE_SHA,baseline_receipt_sha256=BASE_RECEIPT,native_rebuilt=False,native_unchanged=True,home_rebuilt=False,
  boot_authority_unchanged=False,installation_envelope_unchanged=True,packaging_only_changes=False,recipe_sha256=sha(Path(__file__).read_bytes()),
  store=inventory(new),sd=inventory(sd),packing_sha256=sha(encoded(packing)),changed_store_paths=sorted(CHANGED),added_store_paths=sorted(ADDED),
  changed_sd_paths=[],added_sd_files=sorted(overlay),original_sd_files_preserved=len(old_sd),all_existing_sd_executables_preserved=True,
  sd_overlay_required=True,sd_deliverable_created=True,selected_sd_images=selected,providers=33,apps=27,
  components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},
  full_image_bytes=len(result),full_image_sha256=sha(result),hardware_tested=False,physical_adapter_verified=False,
  obd_build=app_build,scene_build=scene_build,serial_build=driver_build,obd_component_sources=sources)
 # Remove .96-only claims whose exact values no longer describe this composition.
 receipt['baseline_source_publication']=receipt.pop('source_publication',None)
 receipt['source_publication']={'product':{'repository':'michaelrolphone-cmyk/RiskRTE-XTEINK-X4-PRO','commit':a.product_revision,'tree':git(ROOT,'rev-parse','HEAD^{tree}')},'components':sources,'verification':'See the separately recorded remote-source verification receipt'}
 receipt['files_1_5_31_unchanged']=True
 for k in ('all_sd_executables_preserved','preserved_store_files','sd_overlay','files_replaced','product_published','system_published','publication_ready','final_published_system_source_pending','final_rebuild_required','local_preflight_only'):receipt.pop(k,None)
 a.output.mkdir(parents=True);write_files(a.output/'store',new);write_files(a.output/'SD',sd);write_files(a.output/'components',parts)
 (a.output/IMAGE).write_bytes(result)
 with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p,data in sorted(overlay.items()):
   entry=zipfile.ZipInfo(p,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
 with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n)for n in z.namelist()}==overlay,'SD archive roundtrip failed')
 receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay))
 (a.output/'receipts').mkdir();(a.output/'receipts/obd-composition.json').write_bytes(encoded(receipt));(a.output/'receipts/packing.json').write_bytes(encoded(packing))
 print(json.dumps({'version':VERSION,'sha256':sha(result),'bytes':len(result),'sd_files':len(overlay),'hardware_tested':False}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('baseline','runtime-source','tools','app','scene','driver','output'):p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
 p.add_argument('--product-revision',required=True);compose(p.parse_args())
