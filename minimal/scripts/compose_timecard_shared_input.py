#!/usr/bin/env python3
"""Compose only Timecard shared input over the published X4 Files .102 cohort.

Preserves all installed packages, immutable host selections, native flash bytes,
startup packing order, grants outside the one Timecard text-input addition, fonts and
at least two free SPIFFS blocks. Artifacts remain held, never flashed/delivered.
"""
import argparse,copy,hashlib,json,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools,BOOTFS,BANK_STATE
from compose_keyboard_100 import verify_image
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build
from build_timecard_shared_input import VERSIONS,SYSTEM,PRIOR
VERSION=VERSIONS['x4']
ROOT=Path(__file__).resolve().parents[2]
BASE='38aefe4bcffbebd46ebe7d54c25bd789f47241e7'
BASE_IMAGE_SHA='5bd5d2b565854fde0e66e723fe0801d1ff78eab7774e68e616497a5b0261dc10'
IMAGE='X4-0.1.102-FULL-INITIAL-ERASES-DATA.bin'
ZIP='X4-0.1.102-Combined-Changed-SD.zip'
CHANGED={'timecard.json','boot.json','cohort.json'}
SD_CHANGED={'Apps/timecard/timecard.elf','Apps/timecard/manifest.json'}
GRANT={'capability':'ui.text-input','api':1,'instance_id':0}


def payload(old,old_sd,components,revision):
    require(set(components)=={'timecard.elf','timecard.json'},'Unexpected component members')
    expected=json.loads(old['timecard.json']);require(expected['version']=='0.2.15','Wrong Timecard predecessor')
    require(old['timecard.json']==old_sd['Apps/timecard/manifest.json'],'Mismatched Timecard manifests')
    expected['version']=VERSION;expected['requires'].append({'capability':'ui.text-input','api':1})
    require(json.loads(components['timecard.json'])==expected,'Timecard authority exceeds additive delta')
    new=dict(old);sd=dict(old_sd)
    new['timecard.json']=components['timecard.json'];sd['Apps/timecard/manifest.json']=components['timecard.json'];sd['Apps/timecard/timecard.elf']=components['timecard.elf']
    boot=json.loads(old['boot.json']);original=copy.deepcopy(boot)
    rows=[r for r in boot['app_capabilities'] if r['manifest']=='timecard.json']
    require(len(rows)==1 and GRANT not in rows[0]['grants'],'Unexpected Timecard authority')
    rows[0]['grants'].append(copy.deepcopy(GRANT));new['boot.json']=encoded(boot);rows[0]['grants'].pop();require(boot==original,'Unrelated authority changed')
    cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.102' and cohort['source_revision']==BASE,'Wrong baseline cohort')
    cohort['source_revision']=revision;new['cohort.json']=encoded(cohort)
    require(set(new)==set(old) and {n for n in new if new[n]!=old[n]}==CHANGED,'Unexpected store delta')
    require(set(sd)==set(old_sd) and {n for n in sd if sd[n]!=old_sd[n]}==SD_CHANGED,'Unexpected SD delta')
    return new,sd


def streamed_image_digest(parts,metadata):
    digest=hashlib.sha256();position=0;ff=b'\xff'*65536
    for name in sorted(parts,key=lambda n:metadata[n]['offset']):
        offset=metadata[name]['offset'];raw=parts[name]
        require(offset>=position and offset+len(raw)<=0x1000000,'Overlapping flash partitions')
        gap=offset-position
        while gap:
            chunk=ff[:min(len(ff),gap)];digest.update(chunk);gap-=len(chunk)
        digest.update(raw);position=offset+len(raw)
    gap=0x1000000-position
    while gap:
        chunk=ff[:min(len(ff),gap)];digest.update(chunk);gap-=len(chunk)
    return digest.hexdigest()


def compose(a):
    require(not a.output.exists(),'Use fresh output directory')
    revision=git(ROOT,'rev-parse','HEAD');clean_source(ROOT,revision,'Product')
    raw=(a.baseline/'receipts/evening-composition.json').read_bytes();base=json.loads(raw)
    require(base['product_source']==BASE and base['full_image_sha256']==BASE_IMAGE_SHA,'Wrong published baseline')
    clean_source(a.runtime,base['runtime_commit'],'Runtime')
    require(git(a.runtime,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Runtime tree differs')
    old,old_sd,parts=[read_tree(a.baseline/n) for n in ['store','SD','components']]
    require(streamed_image_digest(parts,base['components'])==BASE_IMAGE_SHA,'Wrong baseline sparse image')
    require(inventory(old)==base['store'] and inventory(old_sd)==base['sd'] and len(old)==106 and len(old_sd)==90,'Wrong baseline inventory')
    require(sha(old_sd['Apps/timecard/timecard.elf'])==PRIOR['x4'],'Wrong Timecard predecessor')
    require(set(parts)==set(base['components']),'Wrong component inventory')
    for n,row in base['components'].items():
        require(len(parts[n])==row['bytes'] and sha(parts[n])==row['sha256'],'Component custody differs: '+n)
    record=json.loads((a.timecard_build/'timecard-build-record.json').read_bytes())
    require(record['device']=='x4' and record['version']==VERSION and record['sources']['system-apps']==SYSTEM and record['sources']['runtime']==base['runtime_commit'] and record['product_recipe']==revision,'Wrong Timecard source/profile')
    require(all(record[k] for k in ['shared_text_input','original_fonts_retained','baseline_features_preserved']),'Timecard preservation proof missing')
    data={n:(a.timecard_build/n).read_bytes() for n in ['timecard.elf','timecard.json']}
    require(sha(data['timecard.elf'])==record['sha256'] and len(data['timecard.elf'])==record['bytes'] and sha(data['timecard.json'])==record['manifest_sha256'],'Timecard custody differs')
    new,sd=payload(old,old_sd,data,revision)
    pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime)
    image,packing=ordered_build(new,pack);require(ordered_build(dict(reversed(list(new.items()))),pack)==(image,packing),'Nondeterministic packing')
    prior_packing=json.loads((a.baseline/'receipts/packing.json').read_bytes())
    for k in ['ordered_paths','order_recipe_sha256','generator_sha256','config','metadata','file_count','image_bytes']:require(packing[k]==prior_packing[k],'Startup packing changed: '+k)
    require(packing['empty_blocks']>=2,'Reserve violated')
    require(decode(image,0x510000)==new,'Independent packed store readback differs')
    firmware=parts['firmware.bin'];state=bank(firmware,image,True);row=parse(state[:96],True)
    require(row[3]==len(firmware) and row[6]==hashlib.sha256(firmware).digest() and row[7]==hashlib.sha256(image).digest(),'Bank native/store digest mismatch')
    with tempfile.TemporaryDirectory(prefix='x4-timecard-shared-') as temp:
        t=Path(temp);write_files(t/'store',new);write_files(t/'SD',sd);selected=audit_selected_images(json.loads(new['boot.json']),t/'store',t/'SD')
    before={r['manifest']:r for r in base['selected_sd_images']};after={r['manifest']:r for r in selected}
    require(len(selected)==48 and set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'timecard.json'},'Unrelated selected image changed')
    require(after['timecard.json']['sha256']==record['sha256'],'Timecard SD selection differs')
    overlay_paths=set(base['sd_overlay']['files'])|SD_CHANGED;overlay={n:sd[n] for n in sorted(overlay_paths)};require(len(overlay)==16,'Unexpected cumulative overlay')
    parts.update({'bootfs.bin':image,'bank_state.bin':state})
    full_sha=streamed_image_digest(parts,base['components'])
    receipt=copy.deepcopy(base)
    receipt.update(schema='x4.timecard-shared-input-composition',product_source=revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,baseline_full_image_sha256=BASE_IMAGE_SHA,baseline_receipt_sha256=sha(raw),recipe_sha256=sha(Path(__file__).read_bytes()),store=inventory(new),sd=inventory(sd),selected_sd_images=selected,changed_store_paths=sorted(CHANGED),changed_sd_paths=sorted(SD_CHANGED),added_sd_files=[],original_sd_files_preserved=len(old_sd)-2,boot_authority_unchanged=False,boot_authority_delta=[{'manifest':'timecard.json','grant':GRANT}],boot_image_selection_changed=[],timecard_build={'timecard':record},components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),full_image_bytes=0x1000000,full_image_sha256=full_sha,current_component_versions=dict(base['current_component_versions'],timecard=VERSION),native_rebuilt=False,native_unchanged=True,independent_full_image_verified=True,hardware_tested=False,target_instructions_executed=False,full_image_materialized=False,delivered=False,delivery_hold_until_utc='2026-10-12T23:30:00Z')
    receipt['component_sources']['timecard']=dict(repository='michaelrolphone-cmyk/RiscRTE-Productivity',commit=record['sources']['productivity'],version=VERSION,system_commit=SYSTEM,build_record_sha256=sha((a.timecard_build/'timecard-build-record.json').read_bytes()))
    a.output.mkdir(parents=True)
    for n,items in [('store',new),('SD',sd),('components',parts)]:write_files(a.output/n,items)
    with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,data in overlay.items():
            entry=zipfile.ZipInfo(n,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
    with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'SD ZIP readback differs')
    receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96',immediate_delta_from='0.1.102 RF shared input',immediate_delta_paths=sorted(SD_CHANGED))
    write_files(a.output/'receipts',{'evening-composition.json':encoded(receipt),'packing.json':encoded(packing),'timecard-build.json':encoded(record)})
    require(read_tree(a.output/'store')==new and read_tree(a.output/'SD')==sd,'Written output differs')
    clean_source(ROOT,revision,'Product')
    print(json.dumps(dict(sha256=full_sha,sd_overlay_files=len(overlay),free_blocks=packing['empty_blocks'],native_unchanged=True,hardware_tested=False)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['baseline','timecard-build','runtime','tools','output']:p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
    compose(p.parse_args())
