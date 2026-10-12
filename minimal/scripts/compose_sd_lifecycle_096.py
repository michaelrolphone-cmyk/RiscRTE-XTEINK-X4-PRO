#!/usr/bin/env python3
"""X4 .96: preserve .95 code/packing and declare selected SD resident lifecycles."""
import argparse,copy,hashlib,json,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools,BOOTFS,BANK_STATE
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build
from sd_resident_lifecycle import repair,validate

ROOT=Path(__file__).resolve().parents[2]
BASE='7e7b632e2625ffd3769194456a289ba60671cb04'
BASE_SHA='f20a37e7ff99cfa29664dc2e63f33f78ffd8dffcb04bb8124e3a533dfbcb166c'
BASE_RECEIPT='eede29368e30bf1d496f16c7d7914b9c0e888680b8205761bceff5287ad1dc70'
VERSION='0.1.96';IMAGE='X4-0.1.96-FULL-INITIAL-ERASES-DATA.bin'
ZIP='X4-0.1.96-SD-Manifest-Overlay.zip'
PRESERVED=((0,BOOTFS[0]),(BOOTFS[1],BANK_STATE[0]),(BANK_STATE[1],0x1000000))


def baseline(folder,sd_root):
    raw=(folder/'receipts/boot-order-composition.json').read_bytes()
    require(sha(raw)==BASE_RECEIPT,'Wrong qualified .95 receipt')
    receipt=json.loads(raw);full=(folder/'X4-0.1.95-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
    store,sd,parts=read_tree(folder/'store'),read_tree(sd_root),read_tree(folder/'components')
    require(len(full)==0x1000000 and sha(full)==BASE_SHA==receipt['full_image_sha256'],'Wrong .95 full image')
    require(inventory(store)==receipt['store'] and len(store)==103,'Baseline store differs')
    require(inventory(sd)==receipt['sd'] and len(sd)==81,'Baseline SD differs')
    require(set(parts)==set(receipt['components']),'Baseline component set differs')
    for name,row in receipt['components'].items():
        part=parts[name];start=row['offset']
        require(len(part)==row['bytes'] and sha(part)==row['sha256'] and full[start:start+len(part)]==part,
                'Baseline component differs: '+name)
    return receipt,store,sd,parts,full


def payload(old,sd,revision):
    new,new_sd,rows=repair(old,sd)
    cohort=json.loads(old['cohort.json'])
    require(cohort['version']=='0.1.95' and cohort['source_revision']==BASE,'Baseline cohort identity differs')
    cohort.update(version=VERSION,source_revision=revision);new['cohort.json']=encoded(cohort)
    verify_payload(old,new,sd,new_sd,rows,revision)
    return new,new_sd,rows


def verify_payload(old,new,old_sd,new_sd,rows,revision):
    allowed={'cohort.json'}|{r['manifest'] for r in rows};sd_allowed={r['sd_manifest'] for r in rows}
    require(new.keys()==old.keys() and {n for n in old if old[n]!=new[n]}==allowed,'Unapproved internal change')
    require(new_sd.keys()==old_sd.keys() and {n for n in old_sd if old_sd[n]!=new_sd[n]}==sd_allowed,'Unapproved SD change')
    expected=json.loads(old['cohort.json']);expected.update(version=VERSION,source_revision=revision)
    require(new['cohort.json']==encoded(expected),'Cohort changed beyond product identity')
    for row in rows:
        previous=json.loads(old[row['manifest']]);expected=dict(previous,runtime_lifecycle='foreground')
        require(new[row['manifest']]==new_sd[row['sd_manifest']]==encoded(expected),
                'Changed app identity/version/grants beyond lifecycle')
        require(sha(new_sd[row['image']])==row['elf_sha256'],'Changed selected ELF')
    require(validate(new,new_sd)==rows,'Selected foreground evidence differs')


def verify_image(full,previous,old,new,read_image,parse_record,firmware):
    require(len(full)==len(previous)==0x1000000,'Image must be exactly 16 MiB')
    for start,end in PRESERVED:require(full[start:end]==previous[start:end],'Non-store flash changed')
    require(read_image(previous[slice(*BOOTFS)],0x510000)==old,'Baseline decode differs')
    require(read_image(full[slice(*BOOTFS)],0x510000)==new,'Final decode differs')
    state=full[slice(*BANK_STATE)];record=parse_record(state[:96],True)
    require(record[2]==0 and record[3]==len(firmware) and record[6]==hashlib.sha256(firmware).digest() and
            record[7]==hashlib.sha256(full[slice(*BOOTFS)]).digest() and state[96:]==b'\xff'*(8192-96),
            'Bank state digest/initial state differs')


def compose(a):
    require(not a.output.exists(),'Output must be new')
    clean_source(ROOT,a.product_revision,'Product')
    require(git(ROOT,'merge-base',BASE,a.product_revision)==BASE,'Product not descended from .95')
    base,old,sd,parts,full=baseline(a.baseline,a.sd)
    clean_source(a.runtime_source,base['runtime_commit'],'Runtime')
    require(git(a.runtime_source,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Runtime tree differs')
    new,new_sd,rows=payload(old,sd,a.product_revision)
    build,read_image,initial_bank_state,parse_record=load_assembly_tools(a.tools,a.runtime_source)
    image,packing=ordered_build(new,build);firmware=parts['firmware.bin']
    state=initial_bank_state(firmware,image,True);result=bytearray(full)
    result[slice(*BOOTFS)],result[slice(*BANK_STATE)]=image,state
    verify_image(bytes(result),full,old,new,read_image,parse_record,firmware)
    with tempfile.TemporaryDirectory(prefix='x4-096-selected-') as tmp:
        root=Path(tmp);write_files(root/'store',new);write_files(root/'SD',new_sd)
        selected=audit_selected_images(json.loads(new['boot.json']),root/'store',root/'SD')
    require(selected==base['selected_sd_images'] and len(selected)==46,'Selected executable images changed')
    parts=dict(parts,**{'bootfs.bin':image,'bank_state.bin':state})
    receipt=copy.deepcopy(base)
    receipt.update(product_version=VERSION,product_source=a.product_revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),
      product_base=BASE,baseline_full_image_sha256=BASE_SHA,baseline_receipt_sha256=BASE_RECEIPT,
      native_rebuilt=False,native_unchanged=True,home_rebuilt=False,packaging_only_changes=True,
      recipe_sha256=sha(Path(__file__).read_bytes()),store=inventory(new),sd=inventory(new_sd),
      packing_sha256=sha(encoded(packing)),sd_lifecycle=rows,changed_store_paths=sorted({'cohort.json'}|{r['manifest'] for r in rows}),
      changed_sd_paths=sorted(r['sd_manifest'] for r in rows),sd_overlay_required=True,sd_deliverable_created=True,
      original_sd_files_preserved=68,all_sd_executables_preserved=True,preserved_store_files=89,
      components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},
      full_image_bytes=len(result),full_image_sha256=sha(result),hardware_tested=False)
    a.output.mkdir(parents=True);write_files(a.output/'store',new);write_files(a.output/'components',parts)
    write_files(a.output/'SD',new_sd)
    overlay={row['sd_manifest']:new_sd[row['sd_manifest']] for row in rows}
    with zipfile.ZipFile(a.output/ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(overlay.items()):
            entry=zipfile.ZipInfo(name,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,data)
    with zipfile.ZipFile(a.output/ZIP) as z:require({n:z.read(n) for n in z.namelist()}==overlay,'Overlay round trip differs')
    receipt['sd_overlay']=dict(name=ZIP,bytes=(a.output/ZIP).stat().st_size,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay))
    write_files(a.output/'receipts',{'sd-lifecycle-composition.json':encoded(receipt),'packing.json':encoded(packing),
      'baseline-boot-order-composition.json':encoded(base)})
    (a.output/IMAGE).write_bytes(result)
    require((a.output/IMAGE).read_bytes()==result and inventory(read_tree(a.output/'SD'))==receipt['sd'],'Written output differs')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','sd','tools','runtime-source','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--product-revision',required=True)
    print(json.dumps(compose(p.parse_args()),indent=2))
if __name__=='__main__':main()
