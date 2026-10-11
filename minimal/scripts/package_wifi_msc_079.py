#!/usr/bin/env python3
"""Assemble only qualified Wi-Fi/MSC fixes over the exact delivered X4 .78."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from package_reader_bin_overlay import (sha, require, encoded, inventory, write_store,
    imports, native_witness, compile_admission, NATIVE_SHA, PANEL_SHA, RUNTIME_TREE)
from package_reader_daily import layout

ROOT = Path(__file__).resolve().parents[2]
VERSION = '0.1.79'
IMAGE = 'X4-0.1.79-WiFi-MSC-Panel-0.1.12-full-0x0.bin'
BASE_NAME = 'X4-0.1.78-Reader-Daily-Paper-Panel-0.1.12-full-0x0.bin'
BASE_SHA = '1d24836ca58c1f6ca841d3d9a41c38a3ad459e95746760de363a32e5ba04e7b5'
SD_NAME = 'X4-0.1.78-Reader-Daily-Paper-SD.zip'
SD_SHA = 'b7e504f16d717df839f974f0dde6e5f33cf9ff303e49fbb7936784447298d2e8'
WIFI_COMMIT = 'f5673befd745a744872e4802332e647d64577a5c'
MSC_COMMIT = '4c2e2dbe3bf587b51873c65a1a1c3faf4035e884'
WIFI_SHA = 'b54e7d6d17eae9acb9541147734f8291a53adfe1ff6c9158d7eac850c4196a8e'
MSC_SHA = 'dd045f3a828048e82d14676757e54a6dab06d01e00b6a3711d28172b4f8ce567'
CHANGED = {'wifi_settings.elf','wifi_settings.json','usb-msc/driver.elf','usb-msc/manifest.json','cohort.json'}

def source_checks(repo, commit, record):
    for name,digest in record.items():
        require(sha(subprocess.check_output(['git','-C',str(repo),'show',commit+':'+name]))==digest,'Source binding: '+name)
    return {'commit':commit,'files_checked':len(record),'tree':subprocess.check_output(['git','-C',str(repo),'rev-parse',commit+'^{tree}'],text=True).strip()}

def prepare(a):
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from verify_provider_relocation_map import audit_loader_map
    require(not a.output.exists(),'Use a new output directory')
    require(subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==a.source_revision,'Wrong composition commit')
    require(not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True),'Commit source first')
    require(json.loads((ROOT/'minimal/product.json').read_text())['version']==VERSION,'Wrong product version')
    require(subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD^{tree}'],text=True).strip()==RUNTIME_TREE,'Wrong deployed Runtime')
    require(not subprocess.check_output(['git','-C',str(a.runtime),'status','--porcelain','--untracked-files=no'],text=True),'Modified Runtime')
    raw=(a.baseline/BASE_NAME).read_bytes();require(sha(raw)==BASE_SHA,'Exact delivered .78 BIN required')
    native,partitions=layout(raw);fs=raw[0x2f0000:0x800000];old=read_image(fs,0x510000)
    require(len(old)==95 and pack(old)[0]==fs,'Baseline inventory/reproduction')
    require(sha(old['panel/driver.elf'])==PANEL_SHA and sha(native)==NATIVE_SHA,'Native/panel mismatch')
    require(sha(old['wifi_settings.elf'])=='35d9117e6eb6f54576f766eecb289d9f5d5b73776d99db1c6bf574059045cae5','Wrong old Wi-Fi')
    require(sha(old['usb-msc/driver.elf'])=='f791783ac4e21d61c0da4576aef091af2d218d7cd84c4e6ac2f0f36b09a00dac','Wrong old MSC')
    wifi=json.loads((a.components/'wifi/wifi_settings-build-record.json').read_text())
    msc=json.loads((ROOT/'minimal/docs/evidence/msc-cleanup-078/target/target-proof.json').read_text())
    require(wifi['repository_commit']==WIFI_COMMIT and not wifi['working_tree_dirty'] and wifi['sha256']==WIFI_SHA,'Wi-Fi target source binding')
    require(msc['reader_commit']==MSC_COMMIT and not msc['source_dirty'] and msc['target_structure_passed'],'MSC target source binding')
    sources={'wifi':source_checks(a.system,WIFI_COMMIT,wifi['source_sha256']),'msc':source_checks(a.msc_source,MSC_COMMIT,msc['source_sha256'])}
    new=dict(old)
    for dest,src,digest in [('wifi_settings.elf','wifi/wifi_settings.elf',WIFI_SHA),('wifi_settings.json','wifi/wifi_settings.json','39a0ba3841d5a9ec08662f88d8a317f1e7978d53e76021e0271bb21479b25190'),('usb-msc/driver.elf','msc/driver.elf',MSC_SHA),('usb-msc/manifest.json','msc/manifest.json','20f06173b611c1eef2f7d2e1b03485efc50119e9d5ff105fd9b0cb6ddf74fc33')]:
        new[dest]=(a.components/src).read_bytes();require(sha(new[dest])==digest,'Component identity: '+dest)
    for name,version in [('wifi_settings.json','1.1.25'),('usb-msc/manifest.json','0.1.6')]:
        before,after=json.loads(old[name]),json.loads(new[name]);before.pop('version');require(after.pop('version')==version and before==after,'Changed manifest authority: '+name)
    meta=json.loads((a.components/'msc/.package.json').read_text());require(meta['id']=='usb-device-msc-esp32s3' and meta['version']=='0.1.6','MSC package identity')
    for entry in meta['entries']:
        data=(a.components/'msc'/entry['name']).read_bytes();require(len(data)==entry['size_bytes'] and sha(data)==entry['sha256'],'MSC package entry digest')
    mapping=audit_loader_map(a.components/'msc/driver.elf')
    require(not any(mapping[k] for k in ('unmapped_relocations','unmapped_relative_values','unmapped_executable_sections','absolute_peripheral_relocations')),'MSC loader mapping')
    cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.78' and cohort['firmware_sha256']==NATIVE_SHA,'Wrong baseline cohort')
    cohort.update(version=VERSION,source_revision=a.source_revision);new['cohort.json']=encoded(cohort)
    require(old.keys()==new.keys() and {n for n in old if old[n]!=new[n]}==CHANGED,'Unexpected changed component')
    sd_bytes=(a.baseline/SD_NAME).read_bytes();require(sha(sd_bytes)==SD_SHA,'Exact complete .78 SD package required')
    with zipfile.ZipFile(a.baseline/SD_NAME) as z:
        require(z.testzip() is None,'SD ZIP CRC');sd={n:z.read(n) for n in z.namelist() if n.startswith(('Apps/','fonts/'))}
    require(sum(n.endswith('.elf') for n in sd)==16,'SD app count')
    for name,data in sd.items():
        require('..' not in Path(name).parts and not Path(name).is_absolute(),'Unsafe SD path')
        if name.endswith('manifest.json'):
            m=json.loads(data);require(m==json.loads(new[m['file_name'].replace('.elf','.json')]),'SD/internal manifest mismatch')
    a.output.mkdir(parents=True)
    for label,data in [('baseline-store',old),('store',new),('sd',sd)]:write_store(a.output/label,data)
    (a.output/'native.bin').write_bytes(native);(a.output/SD_NAME).write_bytes(sd_bytes)
    exported,witness=native_witness(a.runtime,native);(a.output/'exports.json').write_bytes(encoded(sorted(exported)));(a.output/'native-exports.json').write_bytes(encoded(witness))
    (a.output/'preparation.json').write_bytes(encoded({'source_revision':a.source_revision,'sources':sources,'target_records':{'wifi':wifi,'msc':msc},'msc_loader_mapping':mapping,'inventories':{'baseline-store':inventory(old),'store':inventory(new),'sd':inventory(sd)}}))
    print('Prepared exactly two internal fixes, 90 unchanged internal files and byte-identical complete SD package.',flush=True)

def validate(a,sanitized):
    out=a.output/('sanitized' if sanitized else 'plain');exported=json.loads((a.output/'exports.json').read_text())
    info=compile_admission(a.runtime,a.tools,out,exported,sanitized,a.sanitizers)
    modules=[(p,p.name=='driver.elf') for p in sorted((a.output/'store').rglob('*.elf'))]+[(p,False) for p in sorted((a.output/'sd').rglob('*.elf'))]
    require(len(modules)==54,'Module inventory');negative=0
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    for path,driver in modules:
        names=imports(path.read_bytes());require(set(names)<=set(exported),'Unresolved native imports')
        cmd=[str(out/'strict'),'driver' if driver else 'app',str(path)];subprocess.run(cmd,check=True,env=env,timeout=30)
        if path.name=='wifi_settings.elf' or path.parent.name=='usb-msc':
            for symbol in names:subprocess.run(cmd+[symbol],check=True,env=env,timeout=30);negative+=1
    results=[]
    for active,candidate in [('baseline-store','baseline-store'),('baseline-store','store'),('store','store')]:
        result=subprocess.run([str(out/'cohort'),str(a.output/active),str(a.output/candidate)],capture_output=True,text=True,check=True,env=env,timeout=60)
        row=json.loads(result.stdout);require(row['prepared'] and row['cohort_validated'] and row['elf_count']==38 and row['hardware_calls']==row['storage_calls']==0,'Cohort admission')
        (out/(active+'-to-'+candidate+'.log')).write_text(result.stdout+result.stderr);results.append(dict(row,active=active,candidate=candidate))
    info.update(strict_modules=54,wrong_role_rejections=54,unsafe_operation_rejections=54,missing_import_rejections=negative,cohorts=results)
    (out/'validation.json').write_bytes(encoded(info));print(('Normal' if not sanitized else a.sanitizers)+': 54 modules, '+str(negative)+' missing-import rejections, 3 cohort cases PASS',flush=True)

def finish(a):
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from paired_bank_images import initial_bank_state
    prep=json.loads((a.output/'preparation.json').read_text());stores={}
    for name,expected in prep['inventories'].items():
        stores[name]={p.relative_to(a.output/name).as_posix():p.read_bytes() for p in (a.output/name).rglob('*') if p.is_file()};require(inventory(stores[name])==expected,'Staged files changed')
    checks=[json.loads((a.output/mode/'validation.json').read_text()) for mode in ('plain','sanitized')]
    fs,capacity=pack(stores['store']);require(pack(stores['store'])[0]==fs,'Nondeterministic packing')
    for name in ('baseline-store','store'):
        image=a.output/(name+'.bin');image.write_bytes(pack(stores[name])[0]);dest=a.output/(name+'-independent');dest.mkdir()
        subprocess.run([str(a.mkspiffs),'-u',str(dest),'-p','256','-b','4096','-s',str(0x510000),str(image)],check=True,stdout=subprocess.DEVNULL,timeout=60)
        require({p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}==stores[name],'Independent C SPIFFS readback')
    raw=(a.baseline/BASE_NAME).read_bytes();require(sha(raw)==BASE_SHA,'Baseline changed');native=(a.output/'native.bin').read_bytes()
    require(initial_bank_state(native,raw[0x2f0000:0x800000],True)==raw[0xff2000:0xff4000],'Baseline paired record reproduction')
    image=bytearray(raw);image[0x2f0000:0x800000]=fs;image[0xff2000:0xff4000]=initial_bank_state(native,fs,True)
    ranges=[(0,0x2f0000),(0x800000,0xff2000),(0xff2060,len(raw))];require(all(raw[lo:hi]==image[lo:hi] for lo,hi in ranges),'Unexpected image write')
    fw,partitions=layout(bytes(image));require(fw==native and read_image(bytes(image[0x2f0000:0x800000]),0x510000)==stores['store'],'Final image readback')
    require(sha((a.output/SD_NAME).read_bytes())==SD_SHA,'SD changed')
    (a.output/IMAGE).write_bytes(image)
    report=dict(prep,schema='x4.wifi-msc-079.v1',version=VERSION,baseline_sha256=BASE_SHA,image={'name':IMAGE,'bytes':len(image),'flash_offset':0,'sha256':sha(image)},sd_package={'name':SD_NAME,'bytes':(a.output/SD_NAME).stat().st_size,'sha256':SD_SHA,'byte_identical_to_078':True,'apps':16},validation=checks,changed_internal_files=sorted(CHANGED),unchanged_internal_files=90,
        native_version='0.2.5',native_sha256=NATIVE_SHA,native_unchanged=True,panel_version='0.1.12',panel_sha256=PANEL_SHA,panel_unchanged=True,wifi_version='1.1.25',msc_version='0.1.6',partitions=partitions,store_generator=capacity,independent_readbacks=True,paired_sha_crc=True,partition_md5=True,bootloader_native_esp_checksums_sha256=True,
        unchanged_ranges=[{'offset':lo,'bytes':hi-lo,'sha256':sha(raw[lo:hi])} for lo,hi in ranges],assembler_sha256=sha(Path(__file__).read_bytes()),hardware_tested=False,target_instructions_executed=False,full_flash_overwrites_internal_data=True,preserving_ota_supported=False,excluded=['USB throughput batching','dynamic package discovery'])
    (a.output/'build-custody.json').write_bytes(encoded(report));print(json.dumps(report['image']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','components','runtime','tools','system','msc-source','mkspiffs','output'):p.add_argument('--'+name,type=lambda x:Path(x).resolve(),required=True)
    p.add_argument('--source-revision',required=True);p.add_argument('--sanitizers',choices=['undefined','address,undefined'],default='undefined');p.add_argument('--phase',choices=['all','prepare','plain','sanitized','finish'],default='all')
    a=p.parse_args();sys.path[:0]=[str(a.tools/'scripts'),str(a.runtime/'scripts'),str(a.msc_source/'scripts')]
    if a.phase in ('all','prepare'):prepare(a)
    if a.phase in ('all','plain'):validate(a,False)
    if a.phase in ('all','sanitized'):validate(a,True)
    if a.phase in ('all','finish'):finish(a)
