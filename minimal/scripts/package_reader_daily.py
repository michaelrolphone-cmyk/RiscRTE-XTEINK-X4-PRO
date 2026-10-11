#!/usr/bin/env python3
"""Combine exact qualified Reader and Daily Paper deliveries into X4 0.1.78."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

from package_reader_bin_overlay import (sha, require, encoded, inventory, write_store,
    imports, native_witness, compile_admission, NATIVE_SHA, PANEL_SHA, RUNTIME_TREE)

ROOT = Path(__file__).resolve().parents[2]
VERSION = '0.1.78'
IMAGE = 'X4-0.1.78-Reader-Daily-Paper-Panel-0.1.12-full-0x0.bin'
SD_ZIP = 'X4-0.1.78-Reader-Daily-Paper-SD.zip'
INPUTS = {
 'X4-0.1.76-Reader-Panel-0.1.12-full-0x0.bin': '5a00e718132b8381f0e58a8af1f1b40301580ba9d73f164c20561fae98b962c5',
 'X4-0.1.77-Daily-Paper-Panel-0.1.12-full-0x0.bin': '3af02355beccb3acaba5c258d9d8e70cc60b5eadb8a57d05cb2f2c88ede4b0f3',
 'X4-0.1.77-Reader-Panel-0.1.12-full-0x0.bin': 'b91e38003fe485c90ad554e956b3f866ddf55a670e4af158669676af20b900de',
 'X4-0.1.77-Daily-Paper-SD.zip': 'bed14d99b13b2ea893161e4e76f6a61ed60a7ad6ec4ad8e9b66791b0b21c5671',
 'X4-0.1.73-SD-Apps.zip': '59271bc76abe4ee8aafa360ea4731b25accced2c73ef92683b01139677745469',
 'X4-0.1.73-SD-Fixes-Reader-0.1.1-Hollow-Trail-1.2.1.zip': '7cf266081adef4830291b301fbde80788090e41207caf1b068bf0d7410bcbef5',
 'X4-Reader-0.1.8-Chapter-Links-SD.zip': '006fae730f7ce5f074076ace8d9fcf08341837d14f89638d95f99a6fb0159c19',
}
READER_SHA = '455190996d053b15b79cbad3637386222f3a5286f76016c128f48594801f8bab'
SCENE_SHA = 'fd8543dcb48d02f08cfcda144b0038d457f59b9cc5bf670caeee746f92af3ff7'
DAILY_SHA = '72a8ef9d1c7eb087e889bbc717c635cdb59a4dd6e7d97d3500971c6b743381aa'
OVERLAY = {'ui-scene/driver.elf', 'ui-scene/manifest.json', 'ebook_reader.json', 'hollow_trail.json', 'cohort.json'}

def layout(raw):
    from native_binary_exports import segments
    from paired_bank_images import parse_record
    require(len(raw) == 0x1000000, 'Full 16 MiB image required')
    table = raw[0x8000:0x9000]; entries = []; found = False
    for at in range(0, len(table), 32):
        if table[at:at+2] == b'\xeb\xeb':
            require(table[at+16:at+32] == hashlib.md5(table[:at]).digest(), 'Partition MD5')
            found = True; break
        require(table[at:at+2] == b'\xaa\x50', 'Partition magic')
        _, typ, sub, offset, size, label, flags = struct.unpack('<HBBII16sI', table[at:at+32])
        require(offset + size <= len(raw), 'Partition outside image')
        entries.append(dict(type=typ, subtype=sub, offset=offset, size=size, label=label.rstrip(b'\0').decode(), flags=flags))
    require(found, 'Missing partition digest')
    ordered = sorted(entries, key=lambda x:x['offset'])
    require(all(x['offset']+x['size'] <= y['offset'] for x,y in zip(ordered,ordered[1:])), 'Overlapping partitions')
    pos = 24
    for _ in range(raw[1]): pos += 8 + struct.unpack_from('<I',raw,pos+4)[0]
    end = (pos+16)//16*16+32
    require(end < 0x8000, 'Bootloader overlap'); segments(raw[:end])
    pair = parse_record(raw[0xff2000:0xff2060],True)
    native = raw[0x10000:0x10000+pair[3]]; segments(native)
    require(pair[2] == 0 and sha(native) == NATIVE_SHA, 'Native identity/active bank')
    require(pair[6] == hashlib.sha256(native).digest() and pair[7] == hashlib.sha256(raw[0x2f0000:0x800000]).digest(), 'Paired hashes/CRC')
    require(raw[0x10000+len(native):0x270000] == b'\xff'*(0x260000-len(native)), 'Native padding')
    return native, entries

def prepare(a):
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    require(not a.output.exists(), 'Choose a new output directory')
    for name,digest in INPUTS.items(): require(sha((a.inputs/name).read_bytes()) == digest, 'Input digest: '+name)
    require(subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD^{tree}'],text=True).strip() == RUNTIME_TREE, 'Wrong Runtime tree')
    require(not subprocess.check_output(['git','-C',str(a.runtime),'status','--porcelain','--untracked-files=no'],text=True), 'Modified Runtime')
    require(subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip() == a.source_revision, 'Wrong composition revision')
    require(not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain','--untracked-files=no'],text=True), 'Commit composition first')
    stores = {}; native = None
    for label,name in zip(('baseline-store','daily-store','reader-store'),list(INPUTS)[:3]):
        raw = (a.inputs/name).read_bytes(); fw,_ = layout(raw)
        require(native is None or native == fw, 'Native differs across deliveries'); native=fw
        fs=raw[0x2f0000:0x800000]; stores[label]=read_image(fs,0x510000)
        require(pack(stores[label])[0] == fs, 'Input SPIFFS reproduction')
        require(sha(stores[label]['panel/driver.elf']) == PANEL_SHA, 'Stable panel mismatch')
    base,daily,reader=(stores[k] for k in ('baseline-store','daily-store','reader-store'))
    require(len(base)==len(reader)==92 and len(daily)==95, 'Input inventory')
    new=dict(daily)
    for name in OVERLAY-{'cohort.json','hollow_trail.json'}: new[name]=reader[name]
    for name,version in [('ebook_reader.json','0.1.8'),('ui-scene/manifest.json','0.3.6')]:
        before,after=json.loads(daily[name]),json.loads(new[name])
        require(after.pop('version')==version,'Component version');before.pop('version')
        require(before==after,'Admission policy changed')
    cohort=json.loads(daily['cohort.json']);require(cohort['version']=='0.1.77' and cohort['firmware_sha256']==NATIVE_SHA,'Input cohort')
    cohort.update(version=VERSION,source_revision=a.source_revision);new['cohort.json']=encoded(cohort)
    require(sha(new['ui-scene/driver.elf'])==SCENE_SHA,'Scene identity')
    with zipfile.ZipFile(a.inputs/'X4-0.1.73-SD-Apps.zip') as z:
        require(z.testzip() is None,'Full SD ZIP CRC')
        sd={n:z.read(n) for n in z.namelist() if n.startswith(('Apps/','fonts/'))}
        recorded=json.loads(z.read('X4-SD-Apps-0.1.73.json'))['files']
        require(inventory(sd)==recorded,'Full SD source inventory')
    with zipfile.ZipFile(a.inputs/'X4-0.1.73-SD-Fixes-Reader-0.1.1-Hollow-Trail-1.2.1.zip') as z:
        require(z.testzip() is None,'SD correction ZIP CRC')
        for name in z.namelist():
            if name.startswith('Apps/hollow_trail/'):sd[name]=z.read(name)
    require(sha(sd['Apps/hollow_trail/hollow_trail.elf'])=='77e1bd9ee703dde60d6a48f67b147ac13281a3ca5720e32f681fdf5198952de7','Hollow Trail correction identity')
    before=json.loads(new['hollow_trail.json']);after=json.loads(sd['Apps/hollow_trail/manifest.json'])
    require(after.pop('version')=='1.2.1','Hollow Trail version');before.pop('version')
    require(before==after,'Hollow Trail policy changed')
    new['hollow_trail.json']=sd['Apps/hollow_trail/manifest.json']
    require(new.keys()==daily.keys() and {n for n in new if new[n]!=daily[n]}==OVERLAY,'Unrelated Daily Paper files changed')
    with zipfile.ZipFile(a.inputs/'X4-0.1.77-Daily-Paper-SD.zip') as z:
        require(z.testzip() is None,'Daily ZIP CRC')
        for name in z.namelist():
            if name.startswith('Apps/'):sd[name]=z.read(name)
    with zipfile.ZipFile(a.inputs/'X4-Reader-0.1.8-Chapter-Links-SD.zip') as z:
        require(z.testzip() is None,'Reader ZIP CRC')
        sd['Apps/ebook-reader/ebook_reader.elf']=z.read('Apps/ebook-reader/ebook_reader.elf')
    sd['Apps/ebook-reader/manifest.json']=new['ebook_reader.json']
    require(sum(n.endswith('.elf') for n in sd)==16 and sum(n.endswith('manifest.json') for n in sd)==16,'Complete SD inventory')
    for name,data in sd.items():
        if name.endswith('manifest.json'):
            manifest=json.loads(data);require(json.loads(new[manifest['file_name'].replace('.elf','.json')])==manifest,'Internal/SD manifest mismatch: '+name)
    require(sha(sd['Apps/ebook-reader/ebook_reader.elf'])==READER_SHA and sha(sd['Apps/daily-digest/daily_digest.elf'])==DAILY_SHA,'SD executable identity')
    require(sd['Apps/daily-digest/manifest.json']==new['daily_digest.json'],'Internal/SD Daily manifest')
    boot=json.loads(new['boot.json']);catalog=json.loads((ROOT/'minimal/sd-app-catalog.json').read_text())['apps']
    require(len(boot['app_capabilities'])==26 and len(boot['drivers'])==28 and len(catalog)==24,'App/provider/catalog inventory')
    require({r['file_name'] for r in catalog}=={json.loads(new[r['manifest']])['file_name'] for r in boot['app_capabilities']}-{'default.elf','springboard.elf'},'Catalog/policy agreement')
    require(boot['resident_shell']['foreground'].count('daily_digest.elf')==1,'Daily foreground registration')
    require('daily_digest.elf' not in new and 'ebook_reader.elf' not in new,'SD app split')
    for name,version in [('default.json','0.4.8'),('springboard.json','1.7.31'),('daily_digest.json','0.1.0')]:require(json.loads(new[name])['version']==version,'Preserved app version')
    a.output.mkdir(parents=True)
    for label,files in dict(stores,store=new,sd=sd).items():write_store(a.output/label,files)
    (a.output/'native.bin').write_bytes(native)
    exported,witness=native_witness(a.runtime,native)
    (a.output/'exports.json').write_bytes(encoded(sorted(exported)));(a.output/'native-exports.json').write_bytes(encoded(witness))
    (a.output/'preparation.json').write_bytes(encoded({'source_revision':a.source_revision,'inputs':INPUTS,'inventories':{k:inventory(v) for k,v in dict(stores,store=new,sd=sd).items()}}))
    print('Prepared Reader 0.1.8 + Scene 0.3.6 + Daily Paper 0.1.0; 26 apps / 28 providers.',flush=True)

def validate(a,sanitized):
    directory=a.output/('sanitized' if sanitized else 'plain')
    exported=json.loads((a.output/'exports.json').read_text())
    info=compile_admission(a.runtime,a.tools,directory,exported,sanitized,a.sanitizers)
    modules=[(p,p.name=='driver.elf') for p in sorted((a.output/'store').rglob('*.elf'))]+[(p,False) for p in sorted((a.output/'sd').rglob('*.elf'))]
    require(len(modules)==54,'Module inventory')
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    negatives=0
    for path,provider in modules:
        names=imports(path.read_bytes());require(set(names)<=set(exported),'Unresolved imports')
        command=[str(directory/'strict'),'driver' if provider else 'app',str(path)]
        subprocess.run(command,check=True,env=env,timeout=30)
        if path.name in ('default.elf','springboard.elf','ebook_reader.elf','daily_digest.elf','hollow_trail.elf') or path.parent.name in ('ui-scene','net-http-client'):
            for symbol in names:
                subprocess.run(command+[symbol],check=True,env=env,timeout=30);negatives+=1
    outcomes=[]
    for active,candidate,count,accepted in [('baseline-store','baseline-store',37,True),('daily-store','daily-store',38,True),('reader-store','reader-store',37,True),('store','store',38,True),('daily-store','store',38,True),('baseline-store','store',38,False),('reader-store','store',38,False)]:
        result=subprocess.run([str(directory/'cohort'),str(a.output/active),str(a.output/candidate)],check=True,capture_output=True,text=True,env=env,timeout=45)
        row=json.loads(result.stdout)
        require(row['prepared'] and row['cohort_validated']==accepted and row['hardware_calls']==row['storage_calls']==0,'Cohort admission: '+str(row))
        if accepted:require(row['elf_count']==count,'Cohort module count')
        (directory/(active+'-to-'+candidate+'.log')).write_text(result.stdout+result.stderr)
        outcomes.append(dict(row,active=active,candidate=candidate,expected_acceptance=accepted))
    info.update(strict_modules=54,wrong_role_rejections=54,unsafe_operation_rejections=54,missing_import_rejections=negatives,cohorts=outcomes)
    (directory/'validation.json').write_bytes(encoded(info));print((a.sanitizers if sanitized else 'Normal')+': 54 modules, '+str(negatives)+' missing-import negatives and 7 cohort cases PASS',flush=True)

def finish(a):
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from paired_bank_images import initial_bank_state
    prep=json.loads((a.output/'preparation.json').read_text())
    stores={}
    for label,expected in prep['inventories'].items():
        stores[label]={p.relative_to(a.output/label).as_posix():p.read_bytes() for p in (a.output/label).rglob('*') if p.is_file()}
        require(inventory(stores[label])==expected,'Staged bytes changed')
    validations=[json.loads((a.output/mode/'validation.json').read_text()) for mode in ('plain','sanitized')]
    fs,capacity=pack(stores['store']);require(pack(stores['store'])[0]==fs,'Determinism')
    for label in ('baseline-store','daily-store','reader-store','store'):
        data=pack(stores[label])[0];path=a.output/(label+'.bin');path.write_bytes(data)
        dest=a.output/(label+'-independent');dest.mkdir()
        subprocess.run([str(a.mkspiffs),'-u',str(dest),'-p','256','-b','4096','-s',str(0x510000),str(path)],check=True,stdout=subprocess.DEVNULL,timeout=60)
        require({p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}==stores[label],'Independent C SPIFFS readback')
    raw=(a.inputs/list(INPUTS)[1]).read_bytes();require(sha(raw)==INPUTS[list(INPUTS)[1]],'Daily input changed')
    native=(a.output/'native.bin').read_bytes()
    require(initial_bank_state(native,raw[0x2f0000:0x800000],True)==raw[0xff2000:0xff4000],'Input bank reproduction')
    image=bytearray(raw);image[0x2f0000:0x800000]=fs;image[0xff2000:0xff4000]=initial_bank_state(native,fs,True)
    ranges=[(0,0x2f0000),(0x800000,0xff2000),(0xff2060,len(raw))]
    require(all(raw[lo:hi]==image[lo:hi] for lo,hi in ranges),'Writes outside store and paired record')
    _,partitions=layout(bytes(image));require(read_image(bytes(image[0x2f0000:0x800000]),0x510000)==stores['store'],'Final readback')
    (a.output/IMAGE).write_bytes(image)
    readme='X4 0.1.78: Reader 0.1.8 + Daily Paper 0.1.0. Flash the matching full BIN at 0x0. Full flashing overwrites internal settings, NVS, bonds and AppData; back up needed internal data first. No preserving OTA support. Merge Apps/ and fonts/ into the existing SD root, replacing matching files. Includes all 16 SD applications, matching manifests, Reader fonts and Hollow Trail 1.2.1. Keep other apps, books, fonts and state. Scene 0.3.6 is internal; both firmware and SD updates are required. Hardware operation remains untested.\n'
    with zipfile.ZipFile(a.output/SD_ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(dict(stores['sd'],**{'README.txt':readme.encode()}).items()):
            item=zipfile.ZipInfo(name,(2026,10,11,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o100644<<16;z.writestr(item,data)
    with zipfile.ZipFile(a.output/SD_ZIP) as z:
        require(z.testzip() is None and all(z.read(n)==b for n,b in stores['sd'].items()),'SD ZIP readback')
    report=dict(prep,schema='x4.reader-daily-combined.v1',version=VERSION,validation=validations,
        image={'name':IMAGE,'bytes':len(image),'flash_offset':0,'sha256':sha(image)},
        sd_package={'name':SD_ZIP,'bytes':(a.output/SD_ZIP).stat().st_size,'sha256':sha((a.output/SD_ZIP).read_bytes())},
        runtime_version='0.2.5',native_sha256=NATIVE_SHA,native_unchanged=True,panel_version='0.1.12',panel_sha256=PANEL_SHA,panel_unchanged=True,
        reader_version='0.1.8',scene_version='0.3.6',daily_paper_version='0.1.0',home_version='0.4.8',springboard_version='1.7.31',registered_apps=26,provider_instances=28,launcher_entries=24,
        changed_from_daily=sorted(OVERLAY),unchanged_daily_files=90,sd_apps=16,hollow_trail_version='1.2.1',partitions=partitions,
        partition_md5=True,bootloader_and_native_checksums_sha256=True,paired_sha_crc=True,independent_four_store_readbacks=True,store_generator=capacity,
        unchanged_ranges=[{'offset':lo,'bytes':hi-lo,'sha256':sha(raw[lo:hi])} for lo,hi in ranges],
        hardware_tested=False,target_instructions_executed=False,full_flash_overwrites_internal_data=True,preserving_ota_supported=False)
    (a.output/'build-custody.json').write_bytes(encoded(report));print(json.dumps(report['image']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','runtime','tools','mkspiffs','output'):p.add_argument('--'+name,type=lambda s:Path(s).resolve(),required=True)
    p.add_argument('--sanitizers',choices=['address,undefined','undefined'],default='address,undefined',help='Record actual sanitizer mode; undefined-only is available when host ASan cannot initialize')
    p.add_argument('--source-revision',required=True);p.add_argument('--phase',choices=['all','prepare','plain','sanitized','finish'],default='all')
    a=p.parse_args();sys.path[:0]=[str(a.tools/'scripts'),str(a.runtime/'scripts')]
    if a.phase in ('all','prepare'):prepare(a)
    if a.phase in ('all','plain'):validate(a,False)
    if a.phase in ('all','sanitized'):validate(a,True)
    if a.phase in ('all','finish'):finish(a)
