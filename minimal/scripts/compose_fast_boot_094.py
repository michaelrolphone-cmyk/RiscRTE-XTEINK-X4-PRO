#!/usr/bin/env python3
"""Compose X4 .94 from qualified .93, replacing only native code and Home.

Full initial image; erases internal settings, networks and app data. No flash or
hardware qualification. Existing .90 complete SD tree is required and unchanged.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

sys.dont_write_bytecode = True
from compose_desk_wake_093 import read_tree, clean_source
from compose_files_092 import (require, sha, encoded, inventory, git, write_files,
    load_assembly_tools, BOOTFS, BANK_STATE)
from compose_shared_settings_090 import audit_selected_images
from build_test_bundle import validate_native_composition, cohort_identity

ROOT = Path(__file__).resolve().parents[2]
BASE = '489485d9ca597e88aa94e0379c6f1d860a3e5c47'
BASE_SHA = '13262f6878e99252ec4eb861e3dfe18ead8ac37937ea26636752bd3ccb06f7f4'
BASE_RECEIPT = 'b55115ad4456a2e858e2e9cd72bc2ec1f2a6423daf7ad8c346188b903773cffe'
VERSION, HOME = '0.1.94', '0.4.13'
IMAGE = 'X4-0.1.94-FULL-INITIAL-ERASES-DATA.bin'
HOME_NAMES = ('default.elf','default.json','build-evidence.json')
ALLOWED = {'default.elf','default.json','cohort.json'}
FIRMWARE = (0x10000,0x270000)
PRESERVED = ((0,FIRMWARE[0]),(FIRMWARE[1],BOOTFS[0]),(BOOTFS[1],BANK_STATE[0]),(BANK_STATE[1],0x1000000))
HOOK = '0858a85e56bb12ef1255b02eeb5fb3618a4e46fd283e0a369f4f3bffefe0462b'


def baseline(folder, sd_root):
    receipt_raw=(folder/'receipts/desk-wake-composition.json').read_bytes()
    require(sha(receipt_raw)==BASE_RECEIPT,'Not the exact qualified .93 receipt')
    receipt=json.loads(receipt_raw)
    store,sd,parts=read_tree(folder/'store'),read_tree(sd_root),read_tree(folder/'components')
    full=(folder/'X4-0.1.93-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
    require(len(full)==0x1000000 and sha(full)==BASE_SHA==receipt['full_image_sha256'],'Wrong .93 baseline')
    require(inventory(store)==receipt['store'] and inventory(sd)==receipt['sd'] and len(sd)==81,'Baseline inventory differs')
    require(set(parts)==set(receipt['components']),'Baseline component set differs')
    for name,row in receipt['components'].items():
        raw=parts[name];start=row['offset']
        require(sha(raw)==row['sha256'] and len(raw)==row['bytes'] and full[start:start+len(raw)]==raw,
                'Baseline component mismatch: '+name)
    require(json.loads(store['default.json'])['version']=='0.4.12' and
            json.loads(store['file_browser.json'])['version']=='1.5.30','Baseline package version differs')
    return receipt,store,sd,parts,full


def payload(home,old,lock):
    require(lock['product_version']==VERSION and lock['home_version']==HOME,'Wrong qualification version')
    artifacts={n:(home/n).read_bytes() for n in HOME_NAMES}
    require(inventory(artifacts)==lock['home_artifacts'],'Home differs from qualification lock')
    manifest=json.loads(artifacts['default.json']);evidence=json.loads(artifacts['build-evidence.json'])
    require(manifest==dict(json.loads(old['default.json']),version=HOME),'Home authority/identity changed')
    require(artifacts['default.elf'].startswith(b'\x7fELF') and artifacts['default.elf']!=old['default.elf'],'Unchanged/invalid Home ELF')
    require(evidence['version']==HOME and evidence['repository_commit']==lock['system']['commit'] and
            evidence['working_tree_dirty'] is False and evidence['sha256']==sha(artifacts['default.elf']) and
            evidence['size_bytes']==len(artifacts['default.elf']),'Home source/artifact mismatch')
    require(evidence['desk_clock'] and evidence['sparse_start'] and evidence['deferred_foreground_services'] is True and
            evidence['timer_preferences']=='retained-only' and evidence['grant_count']==19 and
            evidence['grant_bindings']=={'storage.app-data':[62]},'Home selected feature/profile mismatch')
    require(evidence['local_sleep_source_sha256']==HOOK==sha((ROOT/'minimal/apps/portable_sleep.c').read_bytes()),
            'The .93 minute SD-close transaction changed')
    return artifacts,evidence


def changed_store(old,artifacts,candidate,firmware,revision):
    new=dict(old)
    new.update({n:artifacts[n] for n in ('default.elf','default.json')})
    product=dict(schema=1,product='xteink-x4-pro',version=VERSION,source_repo='michaelrolphone-cmyk/RiskRTE-XTEINK-X4-PRO')
    new['cohort.json']=encoded(cohort_identity(product,candidate,firmware,revision))
    require(new.keys()==old.keys() and {n for n in old if old[n]!=new[n]}==ALLOWED,'Unexpected store changes')
    return new


def verify(full,base,old,new,firmware,read_image,parse_record):
    require(len(full)==len(base)==0x1000000,'Full image must be exactly 16 MiB')
    for start,end in PRESERVED:require(full[start:end]==base[start:end],'Unrelated flash changed')
    require(len(firmware)<=FIRMWARE[1]-FIRMWARE[0] and
            full[FIRMWARE[0]:FIRMWARE[0]+len(firmware)]==firmware and
            full[FIRMWARE[0]+len(firmware):FIRMWARE[1]]==b'\xff'*(FIRMWARE[1]-FIRMWARE[0]-len(firmware)),
            'Native partition bytes/padding mismatch')
    require(read_image(base[slice(*BOOTFS)],0x510000)==old,'Baseline SPIFFS bytes differ')
    require(read_image(full[slice(*BOOTFS)],0x510000)==new,'Final SPIFFS bytes differ')
    require(new.keys()==old.keys() and {n for n in old if old[n]!=new[n]}==ALLOWED,'Unapproved internal mutation')
    cohort=json.loads(new['cohort.json'])
    require(cohort['firmware_sha256']==sha(firmware) and cohort['firmware_size']==len(firmware) and
            cohort['version']==VERSION,'Cohort native identity mismatch')
    state=full[slice(*BANK_STATE)];record=parse_record(state[:96],True)
    require(record[2]==0 and record[3]==len(firmware) and record[6]==hashlib.sha256(firmware).digest() and
            record[7]==hashlib.sha256(full[slice(*BOOTFS)]).digest() and state[96:]==b'\xff'*(8192-96),
            'Bank-state digests/initial state differ')
    return dict(independent_full_image_verified=True,boot_authority_unchanged=True,files_1_5_30_unchanged=True,
                changed_store_paths=sorted(ALLOWED),preserved_store_files=len(old)-len(ALLOWED),
                preserved_flash_ranges=[list(x) for x in PRESERVED],full_image_bytes=len(full),full_image_sha256=sha(full))


def sources(a,lock,evidence):
    clean_source(ROOT,a.product_revision,'Product')
    for name in ('runtime','system'):
        root=getattr(a,name+'_source');pin=lock[name]
        clean_source(root,pin['commit'],name)
        require(git(root,'rev-parse','HEAD^{tree}')==pin['tree'],'Wrong '+name+' tree')
    build=evidence['x4_product'];build_source=build['commit']
    require(build['dirty'] is False and build['base']==BASE and build['version']==VERSION and
            build['timer_storage_transaction']=={'capability':'storage.volume','instance':9,'prepare_commit':True,'checked_resume':True} and
            build['recipe_sha256']==sha((ROOT/'minimal/scripts/build_fast_boot_094.py').read_bytes()),'Home product source mismatch')
    import subprocess
    for before,after in ((BASE,build_source),(build_source,a.product_revision)):
        require(subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',before,after],stdout=subprocess.DEVNULL).returncode==0,
                'Product source lineage differs')
    changes=git(ROOT,'diff','--name-only',build_source,a.product_revision).splitlines()
    require(all(n in ('minimal/fast-boot-094-inputs.json','minimal/docs/FAST_BOOT_094.md') or
                n.startswith('minimal/docs/evidence/fast-boot-094/') for n in changes),'Product changed after Home build')
    for name,digest in evidence['desk_sources'].items():
        path=a.system_source/name
        require(path.resolve().is_relative_to(a.system_source.resolve()) and not path.is_symlink() and
                sha(path.read_bytes())==digest,'Home compiled source changed: '+name)
    return build_source,changes


def compose(a):
    require(not a.output.exists(),'Output must be new')
    base,old,sd,parts,full=baseline(a.baseline,a.sd)
    lock_raw=a.lock.read_bytes();lock=json.loads(lock_raw)
    artifacts,evidence=payload(a.home,old,lock)
    home_source,changes=sources(a,lock,evidence)
    candidate_raw=(a.native/'candidate.json').read_bytes();candidate=json.loads(candidate_raw)
    require(sha(candidate_raw)==lock['native_candidate_sha256'],'Native candidate differs from qualification lock')
    expected={k:lock['runtime'][k] for k in ('repository','commit','version')}
    native=validate_native_composition(a.native,candidate,a.runtime_source,native_source_root=a.native_product_source,
                                        expected_runtime=expected)
    require(native['build_options']==lock['native_build_options'],'Native feature options changed')
    for n in ('bootloader.bin','partitions.bin','appdata.bin'):
        require((a.native/n).read_bytes()==parts[n],'Unrelated native asset differs: '+n)
    firmware=(a.native/'firmware.bin').read_bytes()
    require(firmware!=parts['firmware.bin'],'Native improvements absent')
    new=changed_store(old,artifacts,candidate,firmware,a.product_revision)
    build,read_image,initial_bank_state,parse_record=load_assembly_tools(a.tools,a.runtime_source)
    image,packing=build(new);state=initial_bank_state(firmware,image,True)
    result=bytearray(full)
    result[slice(*FIRMWARE)]=firmware+b'\xff'*(FIRMWARE[1]-FIRMWARE[0]-len(firmware))
    result[slice(*BOOTFS)],result[slice(*BANK_STATE)]=image,state
    proof=verify(bytes(result),full,old,new,firmware,read_image,parse_record)
    with tempfile.TemporaryDirectory(prefix='x4-094-sd-audit-') as tmp:
        root=Path(tmp);write_files(root,new)
        selected=audit_selected_images(json.loads(new['boot.json']),root,a.sd)
    require(selected==base['selected_sd_images'] and len(selected)==46,'Selected SD modules changed')
    parts=dict(parts,**{'firmware.bin':firmware,'bootfs.bin':image,'bank_state.bin':state})
    receipt=dict(product='X4',product_version=VERSION,product_source=a.product_revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),
        product_base=BASE,product_source_dirty=False,home_product_source=home_source,packaging_only_changes=changes,
        system_commit=lock['system']['commit'],system_tree=lock['system']['tree'],runtime_commit=expected['commit'],
        runtime_version=expected['version'],runtime_tree=lock['runtime']['tree'],native_platform_commit=native['platform']['commit'],
        native_candidate_sha256=sha(candidate_raw),native_composition=native,native_rebuilt=True,native_unchanged=False,
        firmware_sha256=sha(firmware),firmware_elf_sha256=sha((a.native/'firmware.elf').read_bytes()),
        baseline_full_image_sha256=BASE_SHA,baseline_receipt_sha256=BASE_RECEIPT,qualification_lock_sha256=sha(lock_raw),
        recipe_sha256=sha(Path(__file__).read_bytes()),apps=26,providers=32,store=inventory(new),sd=inventory(sd),
        selected_sd_images=selected,original_sd_files_preserved=81,sd_inventory_verified=True,added_sd_files=[],
        sd_overlay_required=False,sd_deliverable_created=False,shared_settings_enabled=False,
        home_client=dict(version=HOME,artifacts=inventory(artifacts)),files_client=base['files_client'],
        components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},
        full_initial_image_erases_internal_data=True,hardware_tested=False,provider_execution_qualified=False,
        persistence_status='Full initial flash erases internal settings, saved networks and app data.',**proof)
    a.output.mkdir(parents=True);write_files(a.output/'store',new);write_files(a.output/'components',parts)
    write_files(a.output/'receipts/home-client',artifacts)
    write_files(a.output/'receipts',{'fast-boot-composition.json':encoded(receipt),'qualification-lock.json':lock_raw,
                                   'packing.json':encoded(packing),'native-candidate.json':candidate_raw})
    (a.output/IMAGE).write_bytes(result)
    require((a.output/IMAGE).read_bytes()==result and inventory(read_tree(a.output/'store'))==receipt['store'],
            'Written output differs')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','sd','home','lock','native','runtime-source','system-source','native-product-source','tools','output'):
        p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--product-revision',required=True)
    print(json.dumps(compose(p.parse_args()),indent=2))

if __name__=='__main__':main()
