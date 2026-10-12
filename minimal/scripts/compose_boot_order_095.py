#!/usr/bin/env python3
"""X4 .95: immutable .94 code and SD with boot-order SPIFFS placement.

Full initial image at 0x0; erases internal settings, Wi-Fi and app data.
"""
import argparse,copy,hashlib,json
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools,BOOTFS,BANK_STATE
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build

ROOT=Path(__file__).resolve().parents[2]
BASE='16ce5f68002c77d79e10feb7e794437d2b16b8b5'
BASE_SHA='f4a00dfb23d14bc41ce55bedb4b5e36ee15ea32d1c92817119ba0a21431ec634'
BASE_RECEIPT='a47906c630aa1e8cecda3a83dc82b5ef74d8d91a6c7292be1e008b2f547c480a'
VERSION='0.1.95'
IMAGE='X4-0.1.95-FULL-INITIAL-ERASES-DATA.bin'
ALLOWED={'cohort.json'}
PRESERVED=((0,BOOTFS[0]),(BOOTFS[1],BANK_STATE[0]),(BANK_STATE[1],0x1000000))


def baseline(folder,sd_root):
    raw=(folder/'receipts/fast-boot-composition.json').read_bytes()
    require(sha(raw)==BASE_RECEIPT,'Wrong qualified .94 receipt')
    receipt=json.loads(raw);full=(folder/'X4-0.1.94-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
    store,sd,parts=read_tree(folder/'store'),read_tree(sd_root),read_tree(folder/'components')
    require(len(full)==0x1000000 and sha(full)==BASE_SHA==receipt['full_image_sha256'],'Wrong .94 full image')
    require(inventory(store)==receipt['store'] and len(store)==103,'Baseline store differs')
    require(inventory(sd)==receipt['sd'] and len(sd)==81,'Baseline SD differs')
    require(set(parts)==set(receipt['components']),'Baseline component set differs')
    for name,row in receipt['components'].items():
        part=parts[name];start=row['offset']
        require(len(part)==row['bytes'] and sha(part)==row['sha256'] and full[start:start+len(part)]==part,
                'Baseline component differs: '+name)
    return receipt,store,sd,parts,full


def changed_store(old,revision):
    new=dict(old);cohort=json.loads(old['cohort.json'])
    require(cohort['version']=='0.1.94' and cohort['source_revision']==BASE,'Baseline cohort identity differs')
    cohort.update(version=VERSION,source_revision=revision);new['cohort.json']=encoded(cohort)
    return new


def verify(full,previous,old,new,read_image,parse_record,firmware,revision):
    require(len(full)==len(previous)==0x1000000,'Image must be exactly 16 MiB')
    for start,end in PRESERVED:require(full[start:end]==previous[start:end],'Non-store flash changed')
    require(new.keys()==old.keys() and {n for n in old if old[n]!=new[n]}==ALLOWED,'Unapproved file change')
    expected=json.loads(old['cohort.json']);expected.update(version=VERSION,source_revision=revision)
    require(new['cohort.json']==encoded(expected),'Cohort changed beyond product identity')
    require(read_image(previous[slice(*BOOTFS)],0x510000)==old,'Baseline decode differs')
    require(read_image(full[slice(*BOOTFS)],0x510000)==new,'Final decode differs')
    state=full[slice(*BANK_STATE)];record=parse_record(state[:96],True)
    require(record[2]==0 and record[3]==len(firmware) and record[6]==hashlib.sha256(firmware).digest() and
            record[7]==hashlib.sha256(full[slice(*BOOTFS)]).digest() and state[96:]==b'\xff'*(8192-96),
            'Bank state digest/initial state differs')
    return dict(independent_full_image_verified=True,boot_authority_unchanged=True,
      changed_store_paths=sorted(ALLOWED),preserved_store_files=len(old)-1,
      files_1_5_30_unchanged=True,home_0_4_13_unchanged=True,
      preserved_flash_ranges=[list(x) for x in PRESERVED],full_image_bytes=len(full),full_image_sha256=sha(full))


def compose(a):
    require(not a.output.exists(),'Output must be new')
    clean_source(ROOT,a.product_revision,'Product')
    require(git(ROOT,'merge-base',BASE,a.product_revision)==BASE,'Product source not descended from .94')
    base,old,sd,parts,full=baseline(a.baseline,a.sd)
    clean_source(a.runtime_source,base['runtime_commit'],'Runtime')
    require(git(a.runtime_source,'rev-parse','HEAD^{tree}')==base['runtime_tree'],'Runtime tree differs')
    new=changed_store(old,a.product_revision)
    build,read_image,initial_bank_state,parse_record=load_assembly_tools(a.tools,a.runtime_source)
    image,packing=ordered_build(new,build);firmware=parts['firmware.bin']
    state=initial_bank_state(firmware,image,True);result=bytearray(full)
    result[slice(*BOOTFS)],result[slice(*BANK_STATE)]=image,state
    proof=verify(bytes(result),full,old,new,read_image,parse_record,firmware,a.product_revision)
    selected=audit_selected_images(json.loads(new['boot.json']),a.baseline/'store',a.sd)
    require(selected==base['selected_sd_images'] and len(selected)==46,'Selected SD changed')
    parts=dict(parts,**{'bootfs.bin':image,'bank_state.bin':state})
    receipt=copy.deepcopy(base)
    receipt['baseline_qualification_lock_sha256']=receipt.pop('qualification_lock_sha256')
    receipt.update(product_version=VERSION,product_source=a.product_revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),
      product_base=BASE,baseline_full_image_sha256=BASE_SHA,baseline_receipt_sha256=BASE_RECEIPT,
      native_rebuilt=False,native_unchanged=True,home_rebuilt=False,packaging_only_changes=True,
      recipe_sha256=sha(Path(__file__).read_bytes()),store=inventory(new),sd=inventory(sd),
      packing_sha256=sha(encoded(packing)),
      components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},
      hardware_tested=False,**proof)
    a.output.mkdir(parents=True);write_files(a.output/'store',new);write_files(a.output/'components',parts)
    write_files(a.output/'receipts',{'boot-order-composition.json':encoded(receipt),'packing.json':encoded(packing),
      'baseline-fast-boot-composition.json':encoded(base)})
    (a.output/IMAGE).write_bytes(result)
    require((a.output/IMAGE).read_bytes()==result and inventory(read_tree(a.output/'store'))==receipt['store'],'Written output differs')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','sd','tools','runtime-source','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--product-revision',required=True)
    print(json.dumps(compose(p.parse_args()),indent=2))
if __name__=='__main__':main()
