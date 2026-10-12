#!/usr/bin/env python3
"""Compose the scene Lists shared editor over the complete Contexts X4 union.

Preserve every old SD file, all unrelated package/native bytes and exact fonts.
Lists alone receives the text-input grant. Lists and its two hosts gain new immutable SD selections.
"""
import argparse,copy,hashlib,json,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools
from compose_shared_settings_090 import audit_selected_images
from compose_timecard_shared_input import streamed_image_digest
from boot_order_spiffs import build as ordered_build
from build_lists_shared_input import VERSION,PRIOR
from build_lists_resident_owner import OWNER_VERSION,OWNER_PRIOR_SHA
from build_lists_text_host import TEXT_VERSION, HOST_PRIOR
from build_lists_scene_host import SCENE_VERSION, SCENE_PRIOR, SCENE_FLAGS
ROOT=Path(__file__).resolve().parents[2]
BASE='e59b4d682738fa5d287c198846f631cf990f6b1c'
BASE_IMAGE_SHA='08c274c511759713c7c0ff53a9019913275157886125199960a6f62a8950d33c'
ZIP='X4-0.1.102-Combined-Changed-SD.zip'
CHANGED={'default.elf','default.json','lists.json','ui-text/driver.elf','ui-text/manifest.json','ui-scene/driver.elf','ui-scene/manifest.json','boot.json','cohort.json'}
SD_CHANGED=set()
GRANT={'capability':'ui.text-input','api':1,'instance_id':0}

def payload(old,old_sd,components,revision):
 require(set(components)=={'default.elf','default.json','lists.elf','lists.json','ui-text/driver.elf','ui-text/manifest.json','ui-scene/driver.elf','ui-scene/manifest.json'},'Unexpected component members')
 expected=json.loads(old['lists.json']);require(expected['version']=='0.1.1','Wrong Lists predecessor')
 require(old['lists.json']==old_sd['Apps/lists/manifest.json'],'Mismatched selected Lists manifests')
 expected['version']=VERSION;expected['requires'].append({'capability':'ui.text-input','api':1})
 require(json.loads(components['lists.json'])==expected,'Lists authority exceeds additive delta')
 require(json.loads(components['ui-text/manifest.json'])==dict(json.loads(old['ui-text/manifest.json']),version=TEXT_VERSION),'Text host authority changed')
 require(json.loads(components['ui-scene/manifest.json'])==dict(json.loads(old['ui-scene/manifest.json']),version=SCENE_VERSION),'Scene host authority changed')
 require(json.loads(components['default.json'])==dict(json.loads(old['default.json']),version=OWNER_VERSION),'Resident owner authority changed')
 new=dict(old);new.update({n:components[n] for n in ['default.elf','default.json']});sd=dict(old_sd);digest=sha(components['lists.elf']);directory='Apps/lists/image-'+digest
 additions={directory+'/lists.elf',directory+'/manifest.json'};require(not additions&set(sd),'New immutable Lists image already exists')
 new['ui-scene/driver.elf']=components['ui-scene/driver.elf'];new['ui-scene/manifest.json']=components['ui-scene/manifest.json']
 new['ui-text/driver.elf']=components['ui-text/driver.elf'];new['ui-text/manifest.json']=components['ui-text/manifest.json']
 new['lists.json']=components['lists.json'];sd[directory+'/lists.elf']=components['lists.elf'];sd[directory+'/manifest.json']=components['lists.json']
 boot=json.loads(old['boot.json']);original=copy.deepcopy(boot)
 rows=[r for r in boot['app_capabilities'] if r['manifest']=='lists.json'];require(len(rows)==1 and GRANT not in rows[0]['grants'],'Unexpected Lists authority')
 prior_image=copy.deepcopy(rows[0]['image_source']);require(prior_image=={'path':'Apps/lists/lists.elf','volume_instance':9},'Wrong immutable Lists source')
 rows[0]['grants'].append(copy.deepcopy(GRANT));rows[0]['image_source']['path']=directory+'/lists.elf'
 host=next(r for r in boot['drivers'] if r['manifest']=='ui-text/manifest.json');host_before=copy.deepcopy(host['image_source'])
 require(host_before=={'internal_fallback':True,'path':'Drivers/text-input-host/image-'+HOST_PRIOR['x4'][1]+'.elf','volume_instance':9},'Wrong selected text host source')
 require(old_sd[host_before['path']]==old['ui-text/driver.elf'],'Text host internal fallback differs')
 host_path='Drivers/text-input-host/image-'+sha(components['ui-text/driver.elf'])+'.elf';require(host_path not in sd,'Immutable text host collision')
 sd[host_path]=components['ui-text/driver.elf'];additions.add(host_path);host['image_source']['path']=host_path
 scene=next(r for r in boot['drivers'] if r['manifest']=='ui-scene/manifest.json');scene_before=copy.deepcopy(scene['image_source'])
 require(scene_before=={'internal_fallback':True,'path':'Drivers/scene-host/image-'+SCENE_PRIOR['x4'][1]+'.elf','volume_instance':9},'Wrong selected scene host source')
 require(old_sd[scene_before['path']]==old['ui-scene/driver.elf'],'Scene host internal fallback differs')
 scene_path='Drivers/scene-host/image-'+sha(components['ui-scene/driver.elf'])+'.elf';require(scene_path not in sd,'Immutable scene host collision')
 sd[scene_path]=components['ui-scene/driver.elf'];additions.add(scene_path);scene['image_source']['path']=scene_path;new['boot.json']=encoded(boot)
 scene['image_source']=scene_before
 host['image_source']=host_before
 rows[0]['grants'].pop();rows[0]['image_source']=prior_image;require(boot==original,'Unrelated boot authority changed')
 cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.102' and cohort['source_revision']==BASE,'Wrong baseline cohort');cohort['source_revision']=revision;new['cohort.json']=encoded(cohort)
 require(set(new)==set(old) and {n for n in new if new[n]!=old[n]}==CHANGED,'Unexpected store delta')
 require(set(sd)==set(old_sd)|additions and {n for n in old_sd if sd[n]!=old_sd[n]}==SD_CHANGED,'Unexpected SD delta')
 return new,sd,additions

def compose(a):
 require(not a.output.exists(),'Use fresh output directory');revision=git(ROOT,'rev-parse','HEAD');clean_source(ROOT,revision,'Product')
 raw=(a.baseline/'receipts/evening-composition.json').read_bytes();base=json.loads(raw);require(base['product_source']==BASE and base['full_image_sha256']==BASE_IMAGE_SHA,'Wrong published baseline')
 clean_source(a.runtime,base['runtime_commit'],'Runtime');require(git(a.runtime,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Runtime tree differs')
 old,old_sd,parts=[read_tree(a.baseline/n) for n in ['store','SD','components']]
 require(streamed_image_digest(parts,base['components'])==BASE_IMAGE_SHA,'Wrong baseline sparse image')
 require(inventory(old)==base['store'] and inventory(old_sd)==base['sd'] and len(old)==106 and len(old_sd)==92,'Wrong baseline inventory')
 require(sha(old_sd['Apps/lists/lists.elf'])==PRIOR['x4'],'Wrong selected Lists predecessor')
 require(set(parts)==set(base['components']),'Wrong component inventory')
 for n,row in base['components'].items():require(len(parts[n])==row['bytes'] and sha(parts[n])==row['sha256'],'Component custody differs: '+n)
 record=json.loads((a.lists_build/'lists-build-record.json').read_bytes());require(record['device']=='x4' and record['version']==VERSION and record['sources']['runtime']==base['runtime_commit'] and record['product_recipe']==revision,'Wrong Lists source/profile')
 text_record=json.loads((a.text_build/'text-build-record.json').read_bytes());require(text_record['device']=='x4' and text_record['version']==TEXT_VERSION and text_record['sources']=={'runtime':base['runtime_commit'],'system-apps':record['sources']['system-apps']} and text_record['product_recipe']==revision and text_record['defines']==[],'Wrong text host source/profile')
 require(sha(old['ui-text/driver.elf'])==HOST_PRIOR['x4'][1] and json.loads(old['ui-text/manifest.json'])['version']==HOST_PRIOR['x4'][0],'Wrong text host predecessor')
 scene_record=json.loads((a.scene_build/'scene-build-record.json').read_bytes());require(scene_record['device']=='x4' and scene_record['version']==SCENE_VERSION and scene_record['sources']=={'runtime':base['runtime_commit'],'system-apps':record['sources']['system-apps']} and scene_record['product_recipe']==revision and scene_record['defines']==SCENE_FLAGS['x4'] and scene_record['all_compiled_font_bytes_preserved'],'Wrong scene host source/profile')
 require(sha(old['ui-scene/driver.elf'])==SCENE_PRIOR['x4'][1] and json.loads(old['ui-scene/manifest.json'])['version']==SCENE_PRIOR['x4'][0],'Wrong scene host predecessor')
 require(all(record[k] for k in ['shared_text_input','original_fonts_retained','baseline_features_preserved']),'Lists preservation proof missing')
 data={n:(a.lists_build/n).read_bytes() for n in ['lists.elf','lists.json']};require(sha(data['lists.elf'])==record['sha256'] and len(data['lists.elf'])==record['bytes'] and sha(data['lists.json'])==record['manifest_sha256'],'Lists custody differs')
 for name in ['driver.elf','manifest.json']:data['ui-text/'+name]=(a.text_build/name).read_bytes()
 require(sha(data['ui-text/driver.elf'])==text_record['sha256'] and sha(data['ui-text/manifest.json'])==text_record['manifest_sha256'],'Text host custody differs')
 for name in ['driver.elf','manifest.json']:data['ui-scene/'+name]=(a.scene_build/name).read_bytes()
 require(sha(data['ui-scene/driver.elf'])==scene_record['sha256'] and sha(data['ui-scene/manifest.json'])==scene_record['manifest_sha256'],'Scene host custody differs')
 owner_record=json.loads((a.owner_build/'owner-build-record.json').read_bytes());require(owner_record['device']=='x4' and owner_record['version']==OWNER_VERSION and owner_record['system_overlay_commit']==record['sources']['system-apps'] and owner_record['product_recipe']==revision and owner_record['added_defines']==[] and owner_record['fonts_and_all_other_inputs_preserved'] and owner_record['original_flags_and_boot_wake_fixes_preserved'],'Wrong resident owner profile')
 require(sha(old['default.elf'])==OWNER_PRIOR_SHA and owner_record['predecessor']['sha256']==OWNER_PRIOR_SHA,'Wrong resident owner predecessor')
 for name in ['default.elf','default.json']:data[name]=(a.owner_build/name).read_bytes()
 require(sha(data['default.elf'])==owner_record['sha256'] and sha(data['default.json'])==owner_record['manifest_sha256'],'Owner custody differs')
 new,sd,additions=payload(old,old_sd,data,revision)
 pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime);image,packing=ordered_build(new,pack);require(ordered_build(dict(reversed(list(new.items()))),pack)==(image,packing),'Nondeterministic packing')
 prior_packing=json.loads((a.baseline/'receipts/packing.json').read_bytes())
 for k in ['ordered_paths','order_recipe_sha256','generator_sha256','config','metadata','file_count','image_bytes']:require(packing[k]==prior_packing[k],'Startup packing changed: '+k)
 require(packing['empty_blocks']>=2,'Reserve violated');require(decode(image,0x510000)==new,'Independent packed store readback differs')
 firmware=parts['firmware.bin'];state=bank(firmware,image,True);row=parse(state[:96],True);require(row[3]==len(firmware) and row[6]==hashlib.sha256(firmware).digest() and row[7]==hashlib.sha256(image).digest(),'Bank digest mismatch')
 with tempfile.TemporaryDirectory(prefix='x4-lists-shared-') as temp:
  t=Path(temp);write_files(t/'store',new);write_files(t/'SD',sd);selected=audit_selected_images(json.loads(new['boot.json']),t/'store',t/'SD')
 before={r['manifest']:r for r in base['selected_sd_images']};after={r['manifest']:r for r in selected};require(len(selected)==48 and set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'lists.json','ui-text/manifest.json','ui-scene/manifest.json'},'Unrelated selected image changed');require(after['lists.json']['sha256']==record['sha256'],'Lists selection differs')
 overlay_paths=set(base['sd_overlay']['files'])|SD_CHANGED|additions;overlay={n:sd[n] for n in sorted(overlay_paths)};parts.update({'bootfs.bin':image,'bank_state.bin':state});full_sha=streamed_image_digest(parts,base['components'])
 receipt=copy.deepcopy(base)
 receipt.update(schema='x4.lists-shared-input-composition',product_source=revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,baseline_full_image_sha256=BASE_IMAGE_SHA,baseline_receipt_sha256=sha(raw),recipe_sha256=sha(Path(__file__).read_bytes()),store=inventory(new),sd=inventory(sd),selected_sd_images=selected,changed_store_paths=sorted(CHANGED),changed_sd_paths=sorted(SD_CHANGED),added_sd_files=sorted(additions),original_sd_files_preserved=len(old_sd)-len(SD_CHANGED),old_lists_sd_image_preserved=True,boot_authority_unchanged=False,boot_authority_delta=[{'manifest':'lists.json','grant':GRANT}],boot_image_selection_changed=['lists.json','ui-text/manifest.json','ui-scene/manifest.json'],lists_build=record,text_build=text_record,scene_build=scene_record,owner_build=owner_record,components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),full_image_bytes=0x1000000,full_image_sha256=full_sha,current_component_versions=dict(base['current_component_versions'],lists=VERSION,default=OWNER_VERSION,text_input_host=TEXT_VERSION,scene_host=SCENE_VERSION),native_rebuilt=False,native_unchanged=True,independent_full_image_verified=True,hardware_tested=False,target_instructions_executed=False,full_image_materialized=False,delivered=False,delivery_hold_until_utc='2026-10-12T23:30:00Z')
 receipt['component_sources']['lists']=dict(repository='michaelrolphone-cmyk/RiscRTE-Productivity',commit=record['sources']['productivity'],version=VERSION,system_commit=record['sources']['system-apps'],build_record_sha256=sha((a.lists_build/'lists-build-record.json').read_bytes()))
 receipt['component_sources']['text-input-host']=dict(repository='michaelrolphone-cmyk/RiscRTE-System-Apps',commit=text_record['sources']['system-apps'],version=TEXT_VERSION,build_record_sha256=sha((a.text_build/'text-build-record.json').read_bytes()))
 receipt['component_sources']['scene-host']=dict(repository='michaelrolphone-cmyk/RiscRTE-System-Apps',commit=scene_record['sources']['system-apps'],version=SCENE_VERSION,build_record_sha256=sha((a.scene_build/'scene-build-record.json').read_bytes()))
 receipt['predecessor_home_build']=base['home_build'];receipt['predecessor_home_client']=base['home_client'];receipt['home_build']=owner_record;receipt['home_client']=owner_record
 receipt['component_sources']['home']=dict(repository='michaelrolphone-cmyk/RiscRTE-System-Apps',selected_source=owner_record['selected_system_commit'],overlay_commit=owner_record['system_overlay_commit'],version=OWNER_VERSION,build_record_sha256=sha((a.owner_build/'owner-build-record.json').read_bytes()))
 a.output.mkdir(parents=True)
 for n,items in [('store',new),('SD',sd),('components',parts)]:write_files(a.output/n,items)
 with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,data in overlay.items():
   entry=zipfile.ZipInfo(n,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
 with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'SD ZIP readback differs')
 receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96',immediate_delta_from='0.1.102 Contexts shared input',immediate_delta_paths=sorted(SD_CHANGED|additions))
 write_files(a.output/'receipts',{'evening-composition.json':encoded(receipt),'packing.json':encoded(packing),'lists-build.json':encoded(record),'text-build.json':encoded(text_record),'scene-build.json':encoded(scene_record),'owner-build.json':encoded(owner_record)})
 require(read_tree(a.output/'store')==new and read_tree(a.output/'SD')==sd,'Written output differs');clean_source(ROOT,revision,'Product')
 print(json.dumps(dict(sha256=full_sha,sd_overlay_files=len(overlay),free_blocks=packing['empty_blocks'],native_unchanged=True,hardware_tested=False)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['baseline','lists-build','text-build','scene-build','owner-build','runtime','tools','output']:p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
 compose(p.parse_args())
