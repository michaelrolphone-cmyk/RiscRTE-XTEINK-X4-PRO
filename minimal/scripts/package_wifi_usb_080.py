#!/usr/bin/env python3
"""Assemble completed Wi-Fi persistence and USB batching over the delivered X4 .79."""
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
VERSION = '0.1.80'
IMAGE = 'X4-0.1.80-WiFi-USB-Batching-Panel-0.1.12-full-0x0.bin'
BASE_NAME = 'X4-0.1.79-WiFi-MSC-Panel-0.1.12-full-0x0.bin'
BASE_SHA = '8e42978eb7d7196d80bc6bbb61178ff5169e99e288c84b5f16a78c2c03ed8420'
SD_NAME = 'X4-0.1.78-Reader-Daily-Paper-SD.zip'
SD_SHA = 'b7e504f16d717df839f974f0dde6e5f33cf9ff303e49fbb7936784447298d2e8'
WIFI_COMMIT = '600e56bc08962c0473735b2fd5d5d80aa62b77a8'
MSC_COMMIT = '5fe5caa4cd7c8ab03d00e5e8e17cbac16053f743'
WIFI_SHA = 'e5df0a788f2f4d1c2d7faff3109110da54a476c416f4b4894248f92ccb1d694b'
MSC_SHA = 'a8d5613723101f861f5f866ed5e33e1f2c1ec6d00668e799632461146688461c'
WIFI_MANIFEST_SHA = 'cc07014a9a94e37bedc8000893246d1dba1a32d29970d1be2872c3a25a0d618d'
CHANGED = {'wifi_settings.elf','wifi_settings.json','usb-msc/driver.elf','usb-msc/manifest.json','sd/driver.elf','sd/manifest.json','cohort.json'}

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
    raw=(a.baseline/BASE_NAME).read_bytes();require(sha(raw)==BASE_SHA,'Exact delivered .79 BIN required')
    native,partitions=layout(raw);fs=raw[0x2f0000:0x800000];old=read_image(fs,0x510000)
    require(len(old)==95 and pack(old)[0]==fs,'Baseline inventory/reproduction')
    require(sha(old['panel/driver.elf'])==PANEL_SHA and sha(native)==NATIVE_SHA,'Native/panel mismatch')
    require(sha(old['wifi_settings.elf'])=='b54e7d6d17eae9acb9541147734f8291a53adfe1ff6c9158d7eac850c4196a8e','Wrong old Wi-Fi')
    require(sha(old['usb-msc/driver.elf'])=='dd045f3a828048e82d14676757e54a6dab06d01e00b6a3711d28172b4f8ce567','Wrong old MSC')
    wifi=json.loads((a.components/'wifi/wifi_settings-build-record.json').read_text())
    msc=json.loads((ROOT/'minimal/docs/evidence/msc-batching-078/target/msc-target-proof.json').read_text())
    require(wifi['repository_commit']==WIFI_COMMIT and not wifi['working_tree_dirty'] and wifi['sha256']==WIFI_SHA,'Wi-Fi target source binding')
    require(msc['reader_commit']==MSC_COMMIT and not msc['source_dirty'] and msc['target_structure_passed'],'MSC target source binding')
    sources={'wifi':source_checks(a.system,WIFI_COMMIT,wifi['source_sha256']),'msc':source_checks(a.msc_source,MSC_COMMIT,msc['source_sha256'])}
    target=ROOT/'minimal/docs/evidence/msc-batching-078/target'
    binding=json.loads((target/'source-binding.json').read_text())
    require(binding['reader_source_commit']==MSC_COMMIT,'Batching Reader binding')
    sd_commit='3c23b8bd2a1073bd1e3db48d6e9ae034613372c0'
    require(binding['x4_source_commit']==sd_commit,'Batching X4 binding')
    sources['sd']=source_checks(ROOT,sd_commit,{k.removeprefix('x4/'):v for k,v in binding['files'].items()})
    # Bind the exact target build inputs to immutable repository blobs, including
    # the composed SDK. The SDK index itself is provenance, not compiled source.
    import io,tarfile
    sd_build=json.loads((target/'sd-build.json').read_text())
    drivers_commit=binding['drivers_commit']; sdk_blobs=set()
    for repo,commit,paths in [(a.runtime,binding['runtime_commit'],['sdk']),(a.msc_source,MSC_COMMIT,['sdk']),(ROOT,sd_commit,['minimal/interfaces'])]:
        data=subprocess.check_output(['git','-C',str(repo),'archive',commit,*paths])
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            sdk_blobs.update(sha(tar.extractfile(m).read()) for m in tar if m.isfile())
    driver_files={k.split('/drivers/',1)[1]:v for k,v in sd_build['sources'].items() if '/drivers/lib/' in k}
    sources['storage_fatfs']=source_checks(a.drivers,drivers_commit,driver_files)
    sdk_count=0
    for name,digest in sd_build['sources'].items():
        if '/target-sd-0216/sdk/' in name and not name.endswith('/source-hashes.json'):
            require(digest in sdk_blobs,'Unbound SDK input: '+name);sdk_count+=1
        elif '/x4/' in name:
            source_checks(ROOT,sd_commit,{name.split('/x4/',1)[1]:digest})
    sources['sd_sdk']={'headers_checked':sdk_count,'immutable_blob_bindings':True}
    new=dict(old)
    components=[('wifi_settings.elf','wifi/wifi_settings.elf',WIFI_SHA),('wifi_settings.json','wifi/wifi_settings.json',WIFI_MANIFEST_SHA),('usb-msc/driver.elf','msc/driver.elf',MSC_SHA),('usb-msc/manifest.json','msc/manifest.json','8d4fe79759116b59dfffd1982900f7c81a873d7664bfa8aa327733666a0859a1'),('sd/driver.elf','sd/driver.elf','894a177889871d8430fe1122bb0655c8ae9488111544a673d872264428062bed'),('sd/manifest.json','sd/manifest.json','aaaccae4bdc50e42cd5300a543a03a476f3b8ff14cb34c5cb88cd83a929464ae')]
    for dest,src,digest in components:
        new[dest]=(a.components/src).read_bytes();require(sha(new[dest])==digest,'Component identity: '+dest)
    for name,version in [('wifi_settings.json','1.1.26'),('usb-msc/manifest.json','0.1.7'),('sd/manifest.json','0.2.16')]:
        before,after=json.loads(old[name]),json.loads(new[name]);before.pop('version');require(after.pop('version')==version and before==after,'Changed manifest authority: '+name)
    mapping={}
    for folder,pkg,version in [('msc','usb-device-msc-esp32s3','0.1.7'),('sd','x4pro-sd','0.2.16')]:
        meta=json.loads((a.components/folder/'.package.json').read_text());require(meta['id']==pkg and meta['version']==version,'Package identity')
        for entry in meta['entries']:
            data=(a.components/folder/entry['name']).read_bytes();require(len(data)==entry['size_bytes'] and sha(data)==entry['sha256'],'Package entry digest')
        row=audit_loader_map(a.components/folder/'driver.elf');mapping[folder]=row
        require(not any(row[k] for k in ('unmapped_relocations','unmapped_relative_values','unmapped_executable_sections','absolute_peripheral_relocations')),'Provider loader mapping')
    cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.79' and cohort['firmware_sha256']==NATIVE_SHA,'Wrong baseline cohort')
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
    (a.output/'preparation.json').write_bytes(encoded({'source_revision':a.source_revision,'sources':sources,'target_records':{'wifi':wifi,'msc':msc,'sd':sd_build,'batching_binding':binding},'msc_loader_mapping':mapping,'inventories':{'baseline-store':inventory(old),'store':inventory(new),'sd':inventory(sd)}}))
    print('Prepared three completed internal updates, 88 unchanged internal files and byte-identical complete SD package.',flush=True)

def validate(a,sanitized):
    out=a.output/('sanitized' if sanitized else 'plain');exported=json.loads((a.output/'exports.json').read_text())
    info=compile_admission(a.runtime,a.tools,out,exported,sanitized,a.sanitizers)
    modules=[(p,p.name=='driver.elf') for p in sorted((a.output/'store').rglob('*.elf'))]+[(p,False) for p in sorted((a.output/'sd').rglob('*.elf'))]
    require(len(modules)==54,'Module inventory');negative=0
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    for path,driver in modules:
        names=imports(path.read_bytes());require(set(names)<=set(exported),'Unresolved native imports')
        cmd=[str(out/'strict'),'driver' if driver else 'app',str(path)];subprocess.run(cmd,check=True,env=env,timeout=30)
        if path.name=='wifi_settings.elf' or path.parent.name in ('usb-msc','sd'):
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
    report=dict(prep,schema='x4.wifi-usb-batching-080.v1',version=VERSION,baseline_sha256=BASE_SHA,image={'name':IMAGE,'bytes':len(image),'flash_offset':0,'sha256':sha(image)},sd_package={'name':SD_NAME,'bytes':(a.output/SD_NAME).stat().st_size,'sha256':SD_SHA,'byte_identical_to_078':True,'apps':16},validation=checks,changed_internal_files=sorted(CHANGED),unchanged_internal_files=88,
        native_version='0.2.5',native_sha256=NATIVE_SHA,native_unchanged=True,panel_version='0.1.12',panel_sha256=PANEL_SHA,panel_unchanged=True,wifi_version='1.1.26',msc_version='0.1.7',sd_provider_version='0.2.16',partitions=partitions,store_generator=capacity,independent_readbacks=True,paired_sha_crc=True,partition_md5=True,bootloader_native_esp_checksums_sha256=True,
        unchanged_ranges=[{'offset':lo,'bytes':hi-lo,'sha256':sha(raw[lo:hi])} for lo,hi in ranges],assembler_sha256=sha(Path(__file__).read_bytes()),hardware_tested=False,target_instructions_executed=False,full_flash_overwrites_internal_data=True,preserving_ota_supported=False,excluded=['unfinished icon audit','dynamic package discovery'])
    (a.output/'build-custody.json').write_bytes(encoded(report));print(json.dumps(report['image']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','components','runtime','tools','system','msc-source','drivers','mkspiffs','output'):p.add_argument('--'+name,type=lambda x:Path(x).resolve(),required=True)
    p.add_argument('--source-revision',required=True);p.add_argument('--sanitizers',choices=['undefined','address,undefined'],default='undefined');p.add_argument('--phase',choices=['all','prepare','plain','sanitized','finish'],default='all')
    a=p.parse_args();sys.path[:0]=[str(a.tools/'scripts'),str(a.runtime/'scripts'),str(a.msc_source/'scripts')]
    if a.phase in ('all','prepare'):prepare(a)
    if a.phase in ('all','plain'):validate(a,False)
    if a.phase in ('all','sanitized'):validate(a,True)
    if a.phase in ('all','finish'):finish(a)
