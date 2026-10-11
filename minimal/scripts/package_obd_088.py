#!/usr/bin/env python3
"""Add the qualified BLE OBD dashboard to the exact delivered X4 0.1.87 image.

Offline composition only; no device transport. Retains native firmware, all old
provider/application bytes and the private-storage ownership envelope. Strict
admission executes production host code, not Xtensa instructions or real RF.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from package_reader_bin_overlay import (compile_admission, encoded, imports,
    inventory, native_witness, require, sha, write_store)

VERSION = '0.1.88'
BASE_SHA = 'b2700b24e879beb376e55ae94de5f544d55d5a2fa9a4529f0143f5ee10969e0e'
NATIVE_SHA = '121db40999321180d03278f6e644487d0d202dcefc5966ec2a89248236bbc099'
RUNTIME_SHA = '8d713b52edca004e1d53bf30a1c584859fe33d14'
APP_SHA = '879314fa7125c51fa3116903d7007e3f58bc4d0623ccf6bb00df2cb2ba875d1c'
SCENE_SHA = '3236d9806b266e7e19d2c50f6f589b034fd231cdc586b1cf433ab83b0e66c173'
DRIVER_SHA = 'cc5bf2a38bf655c1cb51cbdaf3eacbffff69b852adbfb57363ee366cc453ef1f'
IMAGE = 'X4-0.1.88-OBD-NOVA7-Panel-0.1.12-full-0x0.bin'
SD_ZIP = 'X4-0.1.88-OBD-NOVA7-SD-Overlay-Keep-Existing.zip'
ADDED = set()
CHANGED = {'ui-scene/driver.elf', 'ui-scene/manifest.json', 'obd_dashboard.json', 'boot.json', 'cohort.json'}


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def prepare(a):
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from paired_bank_images import parse_record
    require(not a.output.exists(), 'Use a new output directory')
    require(re.fullmatch('[0-9a-f]{40}', a.source_revision), 'Invalid source revision')
    require(subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD'],text=True).strip()==RUNTIME_SHA,
            'Use the exact Runtime 0.2.18 source')
    require(not subprocess.check_output(['git','-C',str(a.runtime),'status','--porcelain','--untracked-files=no'],text=True),
            'Modified Runtime source')
    raw=a.baseline.read_bytes();require(len(raw)==0x1000000 and sha(raw)==BASE_SHA,'Wrong X4 0.1.87 BIN')
    pair=parse_record(raw[0xff2000:0xff2060], True);require(pair[2]==0,'Baseline bank must be zero')
    native=raw[0x10000:0x10000+pair[3]];require(sha(native)==NATIVE_SHA and pair[6]==hashlib.sha256(native).digest(),'Native bytes differ')
    require(all(marker in native for marker in (b'RISC_APP_POLICY_ROWS:24\0',b'RISC_APP_REQUIREMENT_ROWS:24\0')),'Native policy limits differ')
    fs=raw[0x2f0000:0x800000];old=read_image(fs,0x510000)
    require(pair[7]==hashlib.sha256(fs).digest() and len(old)==106 and pack(old)[0]==fs,'Baseline filesystem differs')
    app=(a.app/'obd_dashboard.elf').read_bytes();scene=(a.scene/'driver.elf').read_bytes()
    require(sha(app)==APP_SHA and sha(scene)==SCENE_SHA,'Use the exact locally qualified target builds')
    require(sha(old['ble-serial/driver.elf'])==DRIVER_SHA,'Baseline BLE driver changed')
    app_manifest=json.loads((a.app/'obd_dashboard.json').read_text())
    require(app_manifest['id']=='obd-dashboard' and app_manifest['version']=='0.2.0' and app_manifest['requires']==[
        {'capability':'ui.scene','api':1},{'capability':'bluetooth.serial','api':1},
        {'capability':'storage.volume','api':1}], 'App requirements mismatch')
    require(app_manifest['runtime_lifecycle']=='foreground' and app_manifest['entry']=='app_main' and app_manifest['architecture']=='xtensa-esp32s3','Native app schema mismatch')
    manifest=json.loads((a.scene/'manifest.json').read_text())
    old_scene=json.loads(old['ui-scene/manifest.json'])
    require(manifest['version']=='0.4.0' and {k:v for k,v in manifest.items() if k!='version'}=={k:v for k,v in old_scene.items() if k!='version'},'Scene policy changed')
    new=dict(old);boot=json.loads(old['boot.json']);previous=copy.deepcopy(boot)
    require(len(boot['drivers'])==33 and len(boot['app_capabilities'])==27,'Unexpected baseline capacity')
    require(boot['installation']['volume_instance']==9 and boot['installation']['settings_sd'] is True,'Wrong installed profile')
    relative='Drivers/scene-host/image-'+SCENE_SHA+'.elf'
    scene_row=next(row for row in boot['drivers'] if row['manifest']=='ui-scene/manifest.json')
    old_scene_path=scene_row['image_source']['path'];scene_row['image_source']['path']=relative
    app_row=next(row for row in boot['app_capabilities'] if row['manifest']=='obd_dashboard.json')
    require(app_row['grants']==[{'capability':'ui.scene','api':1,'instance_id':0},{'capability':'bluetooth.serial','api':1,'instance_id':0}], 'Unexpected baseline OBD grants')
    app_row['grants'].append({'capability':'storage.volume','api':1,'instance_id':9})
    restored=copy.deepcopy(boot)
    next(row for row in restored['drivers'] if row['manifest']=='ui-scene/manifest.json')['image_source']['path']=old_scene_path
    next(row for row in restored['app_capabilities'] if row['manifest']=='obd_dashboard.json')['grants'].pop()
    require(restored==previous,'An unrelated boot policy changed')
    new.update({'ui-scene/driver.elf':scene,'ui-scene/manifest.json':(a.scene/'manifest.json').read_bytes(),
        'obd_dashboard.json':(a.app/'obd_dashboard.json').read_bytes(),'boot.json':encoded(boot)})
    cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.87' and cohort['runtime_version']=='0.2.18','Wrong baseline cohort')
    cohort.update(version=VERSION,source_revision=a.source_revision);new['cohort.json']=encoded(cohort)
    require(set(new)==set(old) and {n for n in old if old[n]!=new[n]}==CHANGED,'Unexpected store changes')
    sd=tree(a.sd)
    require(len(sd)==69 and all(n.startswith(('Apps/','Drivers/')) for n in sd),'Use exact 0.1.87 SD overlay')
    require(not any(Path(n).suffix.lower() in ('.ttf','.otf','.woff','.woff2','.binfont','.epdfont') for n in sd),'Raw fonts are not part of this delivery')
    require(sha(sd['Apps/obd-dashboard/obd_dashboard.elf'])=='cd6049f094f9e668f2010e16794469f6544e3a2be955d8cc25b815aba0516043','Wrong baseline SD app')
    old_sd=dict(sd)
    sd.update({relative:scene,'Apps/obd-dashboard/obd_dashboard.elf':app,'Apps/obd-dashboard/manifest.json':(a.app/'obd_dashboard.json').read_bytes()})
    require({n for n in old_sd if sd[n]!=old_sd[n]}=={'Apps/obd-dashboard/obd_dashboard.elf','Apps/obd-dashboard/manifest.json'},'Unrelated SD files changed')
    # Every selected removable image has a matching exact source. Retain old
    # immutable provider filenames so rollback does not lose its dependencies.
    for row in boot['drivers']:
        if 'image_source' in row:
            require(sd.get(row['image_source']['path'])==new[str(Path(row['manifest']).parent/'driver.elf')], 'SD provider mismatch: '+row['manifest'])
    for row in boot['app_capabilities']:
        if 'image_source' in row:
            path=row['image_source']['path'];require(path in sd,'Missing SD app: '+path)
            sm=json.loads(sd[str(Path(path).parent/'manifest.json')]);bm=json.loads(new[row['manifest']])
            require(sm['id']==bm['id'] and sm['file_name']==bm['file_name'],'SD identity mismatch')
    a.output.mkdir(parents=True);write_store(a.output/'baseline-store',old);write_store(a.output/'store',new);write_store(a.output/'sd',sd)
    (a.output/'native.bin').write_bytes(native)
    exports,witness=native_witness(a.runtime,native);(a.output/'native-exports.json').write_bytes(encoded(witness))
    receipt=dict(schema='x4.obd-nova7.v1',version=VERSION,source_revision=a.source_revision,
        assembler_sha256=sha(Path(__file__).read_bytes()),baseline_sha256=BASE_SHA,native_sha256=NATIVE_SHA,
        native_source=RUNTIME_SHA,native_unchanged=True,changed_internal_files=sorted(CHANGED),added_internal_files=sorted(ADDED),
        unchanged_internal_files=len(old)-len(CHANGED),installation_envelope_unchanged=True,
        provider_instances=33,boot_app_policies=27,provider_capacity=40,app_capacity=64,
        all_file_inventories={'before':inventory(old),'after':inventory(new)},sd_inventory=inventory(sd),
        unchanged_sd_files=sum(sd[n]==old_sd[n] for n in old_sd),app_sha256=APP_SHA,scene_sha256=SCENE_SHA,ble_serial_sha256=DRIVER_SHA,
        app_manifest_derivation='Locally compiled native app, existing scene and BLE grants plus SD instance 9',
        source_publication='Local commits and source patches only; GitHub publication blocked',
        new_component_ci_run=False,
        app_build=json.loads((a.app/'build.json').read_text()),scene_build=json.loads((a.scene/'build.json').read_text()),
        baseline_store_byte_reproduction=True,hardware_tested=False,target_instructions_executed=False,
        full_flash_overwrites_internal_data=True)
    (a.output/'composition.json').write_bytes(encoded(receipt));print('Prepared 33 providers, 27 app policies; 101 original store files unchanged',flush=True)


def validate(a,sanitized):
    new=tree(a.output/'store');exports=json.loads((a.output/'native-exports.json').read_text())['exports']
    mode='sanitized' if sanitized else 'plain';directory=a.output/mode
    info=compile_admission(a.runtime,a.tools,directory,exports,sanitized,installed_catalog=True,shared_files=True,provider_capacity=40)
    modules=[(n,a.output/'store'/n,n.endswith('/driver.elf')) for n in sorted(new) if n.endswith('.elf')]
    modules += [(p.relative_to(a.output/'sd').as_posix(),p,False) for p in sorted((a.output/'sd/Apps').rglob('*.elf'))]
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    missing=0
    for name,path,provider in modules:
        needed=imports(path.read_bytes());require(set(needed)<=set(exports),'Unresolved imports: '+name)
        command=[str(directory/'strict'),'driver' if provider else 'app',str(path)]
        subprocess.run(command,check=True,env=env,timeout=30)
        if name in ('ui-scene/driver.elf','Apps/obd-dashboard/obd_dashboard.elf'):
            for symbol in needed:subprocess.run(command+[symbol],check=True,env=env,timeout=30);missing+=1
    outcomes=[]
    internal=sum(n.endswith('.elf') for n in new)
    for before in ('baseline-store','store'):
        result=subprocess.run([str(directory/'cohort'),str(a.output/before),str(a.output/'store')],check=True,capture_output=True,text=True,env=env,timeout=45)
        (directory/(before+'.log')).write_text(result.stdout+result.stderr)
        row=json.loads(result.stdout);require(row['prepared'] and row['cohort_validated'] and row['elf_count']==internal and row['hardware_calls']==row['storage_calls']==0,'Cohort admission failed: '+str(row))
        outcomes.append(dict(row,active=before))
    from test_obd_nova7_catalog import run as catalog_test
    catalog_test(a.runtime,a.tools,directory,a.output/'store',directory/'catalog',sanitized)
    info.update(catalog_registration_verified=True,strict_modules=len(modules),wrong_role_rejections=len(modules),unsafe_operation_rejections=len(modules),
        missing_import_rejections=missing,internal_elf_count=internal,cohorts=outcomes)
    (a.output/(mode+'-admission.json')).write_bytes(encoded(info));print(mode+': strict modules and complete cohorts PASS',flush=True)


def finish(a):
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from paired_bank_images import initial_bank_state,parse_record
    raw=a.baseline.read_bytes();native=(a.output/'native.bin').read_bytes();new=tree(a.output/'store');old=tree(a.output/'baseline-store')
    receipt=json.loads((a.output/'composition.json').read_text())
    require(sha(raw)==BASE_SHA and inventory(new)==receipt['all_file_inventories']['after'],'Inputs changed after validation')
    validations=[json.loads((a.output/(mode+'-admission.json')).read_text())for mode in ('plain','sanitized')]
    fs,packing=pack(new);require(pack(new)[0]==fs,'Nondeterministic store')
    for label,data,expected in [('old',raw[0x2f0000:0x800000],old),('new',fs,new)]:
        path=a.output/(label+'-bootfs.bin');path.write_bytes(data);dest=a.output/(label+'-readback');dest.mkdir()
        subprocess.run([str(a.mkspiffs),'-u',str(dest),'-p','256','-b','4096','-s',str(0x510000),str(path)],check=True,stdout=subprocess.DEVNULL,timeout=60)
        require(tree(dest)==expected,'Independent SPIFFS readback differs')
    bank=initial_bank_state(native,fs,True);pair=parse_record(bank[:96],True)
    require(pair[6]==hashlib.sha256(native).digest() and pair[7]==hashlib.sha256(fs).digest(),'Pair mismatch')
    image=bytearray(raw);image[0x2f0000:0x800000]=fs;image[0xff2000:0xff4000]=bank
    ranges=[(0,0x2f0000),(0x800000,0xff2000),(0xff4000,len(raw))]
    require(all(image[lo:hi]==raw[lo:hi] for lo,hi in ranges),'Changed bytes outside bootfs/pair record')
    require(read_image(bytes(image[0x2f0000:0x800000]),0x510000)==new,'Final BIN readback differs')
    (a.output/IMAGE).write_bytes(image)
    sd=tree(a.output/'sd');require(inventory(sd)==receipt['sd_inventory'],'SD files changed after validation')
    with zipfile.ZipFile(a.output/SD_ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,blob in sorted(sd.items()):
            item=zipfile.ZipInfo(name,(2026,10,11,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=0o100644<<16;z.writestr(item,blob)
    with zipfile.ZipFile(a.output/SD_ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==sd,'SD ZIP readback differs')
    receipt.update(validation=validations,packing=packing,independent_spiffs_readbacks=True,paired_sha_crc=True,
        unchanged_ranges=[dict(offset=lo,bytes=hi-lo,sha256=sha(raw[lo:hi])) for lo,hi in ranges],
        image=dict(name=IMAGE,bytes=len(image),sha256=sha(image),flash_offset=0),
        sd_package=dict(name=SD_ZIP,sha256=sha((a.output/SD_ZIP).read_bytes())),
        preserving_update_delivered=False,physical_adapter_verified=False)
    (a.output/'build-custody.json').write_bytes(encoded(receipt));print(json.dumps(receipt['image']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('baseline','runtime','tools','app','scene','sd','mkspiffs','output'):
        p.add_argument('--'+key,type=lambda v:Path(v).resolve(),required=True)
    p.add_argument('--source-revision',required=True)
    p.add_argument('--phase',choices=('all','prepare','plain','sanitized','finish'),default='all')
    a=p.parse_args();sys.path[:0]=[str(a.tools/'scripts'),str(a.runtime/'scripts')]
    if a.phase in ('all','prepare'):prepare(a)
    if a.phase in ('all','plain'):validate(a,False)
    if a.phase in ('all','sanitized'):validate(a,True)
    if a.phase in ('all','finish'):finish(a)
