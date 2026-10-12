#!/usr/bin/env python3
"""Compose only RF shared input over the published X4 Files .102 cohort.

Preserves all installed packages, immutable host selections, native flash bytes,
startup packing order, grants outside the one RF text-input addition, fonts and
at least two free SPIFFS blocks. Artifacts remain held, never flashed/delivered.
"""
import argparse,copy,json,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools,BOOTFS,BANK_STATE
from compose_keyboard_100 import verify_image
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build
from build_rf_shared_input import VERSION,SYSTEM,PRIOR
ROOT=Path(__file__).resolve().parents[2]
BASE='6bf5abdf8508f20c1394cc2552a28f1990b73cff'
BASE_IMAGE_SHA='9bb937f8d145d1902e3169a44e03bfea09b593828244e404ee7701d1fc040239'
IMAGE='X4-0.1.102-FULL-INITIAL-ERASES-DATA.bin'
ZIP='X4-0.1.102-Combined-Changed-SD.zip'
CHANGED={'waterfall.json','boot.json','cohort.json'}
SD_CHANGED={'Apps/waterfall/waterfall.elf','Apps/waterfall/manifest.json'}
GRANT={'capability':'ui.text-input','api':1,'instance_id':0}


def payload(old,old_sd,components,revision):
    require(set(components)=={'waterfall.elf','waterfall.json'},'Unexpected component members')
    expected=json.loads(old['waterfall.json']);require(expected['version']=='0.3.3','Wrong RF predecessor')
    require(old['waterfall.json']==old_sd['Apps/waterfall/manifest.json'],'Mismatched RF manifests')
    expected['version']=VERSION;expected['requires'].append({'capability':'ui.text-input','api':1})
    require(json.loads(components['waterfall.json'])==expected,'RF authority exceeds additive delta')
    new=dict(old);sd=dict(old_sd)
    new['waterfall.json']=components['waterfall.json'];sd['Apps/waterfall/manifest.json']=components['waterfall.json'];sd['Apps/waterfall/waterfall.elf']=components['waterfall.elf']
    boot=json.loads(old['boot.json']);original=copy.deepcopy(boot)
    rows=[r for r in boot['app_capabilities'] if r['manifest']=='waterfall.json']
    require(len(rows)==1 and GRANT not in rows[0]['grants'],'Unexpected RF authority')
    rows[0]['grants'].append(copy.deepcopy(GRANT));new['boot.json']=encoded(boot);rows[0]['grants'].pop();require(boot==original,'Unrelated authority changed')
    cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.102' and cohort['source_revision']==BASE,'Wrong baseline cohort')
    cohort['source_revision']=revision;new['cohort.json']=encoded(cohort)
    require(set(new)==set(old) and {n for n in new if new[n]!=old[n]}==CHANGED,'Unexpected store delta')
    require(set(sd)==set(old_sd) and {n for n in sd if sd[n]!=old_sd[n]}==SD_CHANGED,'Unexpected SD delta')
    return new,sd


def compose(a):
    require(not a.output.exists(),'Use fresh output directory')
    revision=git(ROOT,'rev-parse','HEAD');clean_source(ROOT,revision,'Product')
    raw=(a.baseline/'receipts/evening-composition.json').read_bytes();base=json.loads(raw)
    require(base['product_source']==BASE and base['full_image_sha256']==BASE_IMAGE_SHA,'Wrong published baseline')
    clean_source(a.runtime,base['runtime_commit'],'Runtime')
    require(git(a.runtime,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Runtime tree differs')
    old,old_sd,parts=[read_tree(a.baseline/n) for n in ['store','SD','components']]
    previous=(a.baseline/IMAGE).read_bytes();require(sha(previous)==BASE_IMAGE_SHA,'Wrong baseline BIN')
    require(inventory(old)==base['store'] and inventory(old_sd)==base['sd'] and len(old)==106 and len(old_sd)==90,'Wrong baseline inventory')
    require(sha(old_sd['Apps/waterfall/waterfall.elf'])==PRIOR['x4'],'Wrong RF predecessor')
    require(set(parts)==set(base['components']),'Wrong component inventory')
    for n,row in base['components'].items():
        require(len(parts[n])==row['bytes'] and sha(parts[n])==row['sha256'] and previous[row['offset']:row['offset']+len(parts[n])]==parts[n],'Component custody differs: '+n)
    record=json.loads((a.rf_build/'waterfall-build-record.json').read_bytes())
    require(record['device']=='x4' and record['version']==VERSION and record['sources']['system-apps']==SYSTEM and record['sources']['runtime']==base['runtime_commit'] and record['product_recipe']==revision,'Wrong RF source/profile')
    require(all(record[k] for k in ['shared_text_input','original_fonts_retained','baseline_features_preserved']),'RF preservation proof missing')
    data={n:(a.rf_build/n).read_bytes() for n in ['waterfall.elf','waterfall.json']}
    require(sha(data['waterfall.elf'])==record['sha256'] and len(data['waterfall.elf'])==record['bytes'] and sha(data['waterfall.json'])==record['manifest_sha256'],'RF custody differs')
    new,sd=payload(old,old_sd,data,revision)
    pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime)
    image,packing=ordered_build(new,pack);require(ordered_build(dict(reversed(list(new.items()))),pack)==(image,packing),'Nondeterministic packing')
    prior_packing=json.loads((a.baseline/'receipts/packing.json').read_bytes())
    for k in ['ordered_paths','order_recipe_sha256','generator_sha256','config','metadata','file_count','image_bytes']:require(packing[k]==prior_packing[k],'Startup packing changed: '+k)
    require(packing['empty_blocks']>=2,'Reserve violated')
    firmware=parts['firmware.bin'];state=bank(firmware,image,True);full=bytearray(previous);full[slice(*BOOTFS)],full[slice(*BANK_STATE)]=image,state
    verify_image(bytes(full),previous,old,new,firmware,decode,parse)
    with tempfile.TemporaryDirectory(prefix='x4-rf-shared-') as temp:
        t=Path(temp);write_files(t/'store',new);write_files(t/'SD',sd);selected=audit_selected_images(json.loads(new['boot.json']),t/'store',t/'SD')
    before={r['manifest']:r for r in base['selected_sd_images']};after={r['manifest']:r for r in selected}
    require(len(selected)==48 and set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'waterfall.json'},'Unrelated selected image changed')
    require(after['waterfall.json']['sha256']==record['sha256'],'RF SD selection differs')
    overlay_paths=set(base['sd_overlay']['files'])|SD_CHANGED;overlay={n:sd[n] for n in sorted(overlay_paths)};require(len(overlay)==14,'Unexpected cumulative overlay')
    parts.update({'bootfs.bin':image,'bank_state.bin':state})
    receipt=copy.deepcopy(base)
    receipt.update(schema='x4.rf-shared-input-composition',product_source=revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,baseline_full_image_sha256=sha(previous),baseline_receipt_sha256=sha(raw),recipe_sha256=sha(Path(__file__).read_bytes()),store=inventory(new),sd=inventory(sd),selected_sd_images=selected,changed_store_paths=sorted(CHANGED),changed_sd_paths=sorted(SD_CHANGED),added_sd_files=[],original_sd_files_preserved=len(old_sd)-2,boot_authority_unchanged=False,boot_authority_delta=[{'manifest':'waterfall.json','grant':GRANT}],boot_image_selection_changed=[],rf_build={'waterfall':record},components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),full_image_bytes=len(full),full_image_sha256=sha(full),current_component_versions=dict(base['current_component_versions'],waterfall=VERSION),native_rebuilt=False,native_unchanged=True,independent_full_image_verified=True,hardware_tested=False,target_instructions_executed=False,full_image_materialized=a.materialize_full,delivered=False,delivery_hold_until_utc='2026-10-12T23:30:00Z')
    receipt['component_sources']['waterfall']=dict(repository='michaelrolphone-cmyk/RiscRTE-Utilities',commit=record['sources']['utilities'],version=VERSION,system_commit=SYSTEM,build_record_sha256=sha((a.rf_build/'waterfall-build-record.json').read_bytes()))
    a.output.mkdir(parents=True)
    for n,items in [('store',new),('SD',sd),('components',parts)]:write_files(a.output/n,items)
    if a.materialize_full:(a.output/IMAGE).write_bytes(full)
    with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,data in overlay.items():
            entry=zipfile.ZipInfo(n,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
    with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'SD ZIP readback differs')
    receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96',immediate_delta_from='0.1.102 Files shared input',immediate_delta_paths=sorted(SD_CHANGED))
    write_files(a.output/'receipts',{'evening-composition.json':encoded(receipt),'packing.json':encoded(packing),'rf-build.json':encoded(record)})
    require(read_tree(a.output/'store')==new and read_tree(a.output/'SD')==sd and (not a.materialize_full or (a.output/IMAGE).read_bytes()==full),'Written output differs')
    clean_source(ROOT,revision,'Product')
    print(json.dumps(dict(sha256=sha(full),sd_overlay_files=len(overlay),free_blocks=packing['empty_blocks'],native_unchanged=True,hardware_tested=False)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['baseline','rf-build','runtime','tools','output']:p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
    p.add_argument('--materialize-full',action='store_true',help='Explicitly write the erasing full-initial BIN; default reconstructs it only in memory')
    compose(p.parse_args())
