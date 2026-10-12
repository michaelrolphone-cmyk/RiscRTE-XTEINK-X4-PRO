#!/usr/bin/env python3
"""Compose the Timecard 0.2.17 lifecycle correction over the qualified OBD X4 union.

Preserve the old immutable Timecard image and all unrelated package/native bytes.
Only Timecard receives a new immutable SD selection; its authority is unchanged.
"""
import argparse,copy,hashlib,json,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools
from compose_shared_settings_090 import audit_selected_images
from compose_timecard_shared_input import streamed_image_digest
from boot_order_spiffs import build as ordered_build
from build_timecard_policy import VERSION,SYSTEM,SELECTED_PRIOR as PRIOR,SELECTION
ROOT=Path(__file__).resolve().parents[2]
BASE=SELECTION['baseline']['compiled_recipe_commit']
BASE_IMAGE_SHA=SELECTION['baseline']['full_image_sha256']
ZIP='X4-0.1.102-Combined-Changed-SD.zip'
CHANGED={'timecard.json','boot.json','cohort.json'}
SD_CHANGED=set()
GRANT={'capability':'ui.text-input','api':1,'instance_id':0}

def payload(old,old_sd,components,revision):
 require(set(components)=={'timecard.elf','timecard.json'},'Unexpected component members')
 expected=json.loads(old['timecard.json']);require(expected['version']=='0.2.16','Wrong Timecard predecessor')
 require(old['timecard.json']==old_sd['Apps/timecard/image-'+PRIOR['x4']+'/manifest.json'],'Mismatched selected Timecard manifests')
 require(expected['requires'].count({'capability':'ui.text-input','api':1})==1,'Wrong inherited shared-input authority');expected['version']=VERSION
 require(json.loads(components['timecard.json'])==expected,'Timecard authority exceeds additive delta')
 new=dict(old);sd=dict(old_sd);digest=sha(components['timecard.elf']);directory='Apps/timecard/image-'+digest
 additions={directory+'/timecard.elf',directory+'/manifest.json'};require(not additions&set(sd),'New immutable Timecard image already exists')
 new['timecard.json']=components['timecard.json'];sd[directory+'/timecard.elf']=components['timecard.elf'];sd[directory+'/manifest.json']=components['timecard.json']
 boot=json.loads(old['boot.json']);original=copy.deepcopy(boot)
 rows=[r for r in boot['app_capabilities'] if r['manifest']=='timecard.json'];require(len(rows)==1 and rows[0]['grants'].count(GRANT)==1,'Unexpected Timecard authority')
 prior_image=copy.deepcopy(rows[0]['image_source']);require(prior_image=={'path':'Apps/timecard/image-'+PRIOR['x4']+'/timecard.elf','volume_instance':9},'Wrong immutable Timecard source')
 rows[0]['image_source']['path']=directory+'/timecard.elf';new['boot.json']=encoded(boot)
 rows[0]['image_source']=prior_image;require(boot==original,'Unrelated boot authority changed')
 cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.102' and cohort['source_revision']==BASE,'Wrong baseline cohort');cohort['source_revision']=revision;new['cohort.json']=encoded(cohort)
 require(set(new)==set(old) and {n for n in new if new[n]!=old[n]}==CHANGED,'Unexpected store delta')
 require(set(sd)==set(old_sd)|additions and {n for n in old_sd if sd[n]!=old_sd[n]}==SD_CHANGED,'Unexpected SD delta')
 return new,sd,additions

def compose(a):
 require(SELECTION['finalized'] and BASE and SYSTEM,'Final published qualified baseline is not selected');require(sha(a.baseline_handoff.read_bytes())==SELECTION['baseline']['combined_handoff_sha256'],'Wrong qualified OBD handoff');require(not a.output.exists(),'Use fresh output directory');revision=git(ROOT,'rev-parse','HEAD');clean_source(ROOT,revision,'Product')
 raw=(a.baseline/'receipts/evening-composition.json').read_bytes();require(sha(raw)==SELECTION['baseline']['receipt_sha256'],'Changed OBD composition receipt');base=json.loads(raw);require(base['product_source']==BASE and base['full_image_sha256']==BASE_IMAGE_SHA,'Wrong published baseline')
 clean_source(a.runtime,base['runtime_commit'],'Runtime');require(git(a.runtime,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Runtime tree differs')
 old,old_sd,parts=[read_tree(a.baseline/n) for n in ['store','SD','components']]
 require(streamed_image_digest(parts,base['components'])==BASE_IMAGE_SHA,'Wrong baseline sparse image')
 require(inventory(old)==base['store'] and inventory(old_sd)==base['sd'] and len(old)==106 and len(old_sd)==SELECTION['baseline']['sd_file_count'],'Wrong baseline inventory')
 require(sha(old_sd['Apps/timecard/image-'+PRIOR['x4']+'/timecard.elf'])==PRIOR['x4'],'Wrong selected Timecard predecessor')
 require(set(parts)==set(base['components']),'Wrong component inventory')
 for n,row in base['components'].items():require(len(parts[n])==row['bytes'] and sha(parts[n])==row['sha256'],'Component custody differs: '+n)
 record=json.loads((a.timecard_build/'timecard-build-record.json').read_bytes());require(record['device']=='x4' and record['version']==VERSION and record['sources']['system-apps']==SYSTEM and record['sources']['runtime']==base['runtime_commit'] and record['product_recipe']==revision,'Wrong Timecard source/profile')
 require(all(record[k] for k in ['shared_text_input','original_fonts_retained','baseline_features_preserved']),'Timecard preservation proof missing')
 data={n:(a.timecard_build/n).read_bytes() for n in ['timecard.elf','timecard.json']};require(sha(data['timecard.elf'])==record['sha256'] and len(data['timecard.elf'])==record['bytes'] and sha(data['timecard.json'])==record['manifest_sha256'],'Timecard custody differs')
 new,sd,additions=payload(old,old_sd,data,revision)
 pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime);image,packing=ordered_build(new,pack);require(ordered_build(dict(reversed(list(new.items()))),pack)==(image,packing),'Nondeterministic packing')
 prior_packing=json.loads((a.baseline/'receipts/packing.json').read_bytes())
 for k in ['ordered_paths','order_recipe_sha256','generator_sha256','config','metadata','file_count','image_bytes']:require(packing[k]==prior_packing[k],'Startup packing changed: '+k)
 require(packing['empty_blocks']>=2,'Reserve violated');require(decode(image,0x510000)==new,'Independent packed store readback differs')
 firmware=parts['firmware.bin'];state=bank(firmware,image,True);row=parse(state[:96],True);require(row[3]==len(firmware) and row[6]==hashlib.sha256(firmware).digest() and row[7]==hashlib.sha256(image).digest(),'Bank digest mismatch')
 with tempfile.TemporaryDirectory(prefix='x4-timecard-shared-') as temp:
  t=Path(temp);write_files(t/'store',new);write_files(t/'SD',sd);selected=audit_selected_images(json.loads(new['boot.json']),t/'store',t/'SD')
 before={r['manifest']:r for r in base['selected_sd_images']};after={r['manifest']:r for r in selected};require(len(selected)==48 and set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'timecard.json'},'Unrelated selected image changed');require(after['timecard.json']['sha256']==record['sha256'],'Timecard selection differs')
 overlay_paths=set(base['sd_overlay']['files'])|SD_CHANGED|additions;overlay={n:sd[n] for n in sorted(overlay_paths)};parts.update({'bootfs.bin':image,'bank_state.bin':state});full_sha=streamed_image_digest(parts,base['components'])
 receipt=copy.deepcopy(base)
 receipt.update(schema='x4.timecard-input-lifecycle-composition',product_source=revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,baseline_full_image_sha256=BASE_IMAGE_SHA,baseline_receipt_sha256=sha(raw),recipe_sha256=sha(Path(__file__).read_bytes()),store=inventory(new),sd=inventory(sd),selected_sd_images=selected,changed_store_paths=sorted(CHANGED),changed_sd_paths=sorted(SD_CHANGED),added_sd_files=sorted(additions),original_sd_files_preserved=len(old_sd)-len(SD_CHANGED),old_immutable_timecard_image_preserved=True,boot_authority_unchanged=True,boot_authority_delta=[],boot_image_selection_changed=['timecard.json'],timecard_build=record,components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),full_image_bytes=0x1000000,full_image_sha256=full_sha,current_component_versions=dict(base['current_component_versions'],timecard=VERSION),native_rebuilt=False,native_unchanged=True,lists_resident_owner_unchanged=True,shared_text_hosts_unchanged=True,scene_host_unchanged=True,lifecycle_successor=True,independent_full_image_verified=True,hardware_tested=False,target_instructions_executed=False,full_image_materialized=False,delivered=False,delivery_hold_until_utc='2026-10-12T23:30:00Z')
 receipt['component_sources']['timecard']=dict(repository='michaelrolphone-cmyk/RiscRTE-Productivity',commit=record['sources']['productivity'],version=VERSION,system_commit=SYSTEM,build_record_sha256=sha((a.timecard_build/'timecard-build-record.json').read_bytes()))
 a.output.mkdir(parents=True)
 for n,items in [('store',new),('SD',sd),('components',parts)]:write_files(a.output/n,items)
 with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,data in overlay.items():
   entry=zipfile.ZipInfo(n,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
 with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'SD ZIP readback differs')
 receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96',immediate_delta_from='0.1.102 OBD qualified union',immediate_delta_paths=sorted(SD_CHANGED|additions))
 write_files(a.output/'receipts',{'evening-composition.json':encoded(receipt),'packing.json':encoded(packing),'timecard-build.json':encoded(record)})
 require(read_tree(a.output/'store')==new and read_tree(a.output/'SD')==sd,'Written output differs');clean_source(ROOT,revision,'Product')
 print(json.dumps(dict(sha256=full_sha,sd_overlay_files=len(overlay),free_blocks=packing['empty_blocks'],native_unchanged=True,hardware_tested=False)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['baseline','baseline-handoff','timecard-build','runtime','tools','output']:p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
 compose(p.parse_args())
