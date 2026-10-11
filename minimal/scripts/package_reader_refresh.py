#!/usr/bin/env python3
"""Compose Reader refresh support over the qualified X4 0.1.73 image."""
import argparse, hashlib, json, os, sys
from pathlib import Path
from build_recovered_diagnostic import require, sha, encoded, digest_inventory
from package_home_ui import clean, write_store
from package_resident_cohort import descriptor
from build_test_bundle import cohort_identity

ROOT=Path(__file__).resolve().parents[2]
BASE_SHA='01246f28f9672e9c38c240565983b5b35fabb3b6403ed56dc335baf9d10685e4'
NATIVE_ELF_SHA='3b0605d518288202c9154ca192acfe638dadd861caf305b970cdd029f46a05cb'

def build(a):
    require(not a.output.exists(),'Choose a new output directory')
    source=clean(ROOT);runtime=a.runtime.resolve()
    product=json.loads((ROOT/'minimal/product.json').read_text())
    require(product['version']=='0.1.74','Wrong product identity')
    sys.path[:0]=[str(a.tools.resolve()/'scripts'),str(runtime/'scripts'),str(ROOT/'minimal/recovery_tools')]
    from read_only_spiffs import read_image
    from current_bootfs import build as pack
    from paired_bank_images import initial_bank_state, parse_record
    import verify_update_elf as verify
    import recovery_store_admission as admission
    admission.ROOT=a.tools.resolve()
    raw=a.baseline.read_bytes();require(len(raw)==0x1000000 and sha(raw)==BASE_SHA,'Wrong qualified baseline')
    native_elf=(a.native/'firmware.elf').read_bytes();firmware=(a.native/'firmware.bin').read_bytes()
    require(sha(native_elf)==NATIVE_ELF_SHA,'Wrong native reference ELF')
    require(raw[0x10000:0x270000]==firmware+b'\xff'*(0x260000-len(firmware)),'Native bytes differ from qualified baseline')
    candidate=json.loads((a.native/'candidate.json').read_text())
    previous=json.loads(a.baseline_receipt.read_text())
    require(previous['image']['sha256']==BASE_SHA,'Wrong baseline receipt')
    files=read_image(raw[0x2f0000:0x800000],0x510000);frozen=dict(files)
    require(digest_inventory(files)==previous['store_files'],'Baseline inventory differs')
    for name in ('driver.elf','manifest.json'):files['ui-scene/'+name]=(a.scene/name).read_bytes()
    require(json.loads(files['ui-scene/manifest.json'])['version']=='0.3.3','Wrong scene service')
    files['ebook_reader.json']=(a.reader/'ebook_reader.json').read_bytes()
    manifest=json.loads(files['ebook_reader.json'])
    require(manifest['version']=='0.1.4','Wrong Reader app')
    old_manifest=json.loads(frozen['ebook_reader.json'])
    require({k:v for k,v in manifest.items() if k!='version'}=={k:v for k,v in old_manifest.items() if k!='version'},'Reader admission policy changed')
    files['cohort.json']=encoded(cohort_identity(product,candidate,firmware,source['commit']))
    changed={n for n in files if files[n]!=frozen.get(n)}
    require(changed=={'ui-scene/driver.elf','ui-scene/manifest.json','ebook_reader.json','cohort.json'} and files.keys()==frozen.keys(),'Unexpected internal changes')
    require(json.loads(files['panel/manifest.json'])['version']=='0.1.12' and files['panel/driver.elf']==frozen['panel/driver.elf'],'Panel changed')
    app=(a.reader/'ebook_reader.elf').read_bytes();require(len(app)<=2*1024*1024,'Reader exceeds loader bound');descriptor(app,2,check_renderer=False)
    a.output.mkdir(parents=True);write_store(a.output/'store',files)
    (a.output/'ebook_reader.elf').write_bytes(app)
    header='#define RISC_APP_REQUIREMENT_ROWS 24\n#define RISC_APP_POLICY_ROWS 24\n#include "'+str(runtime/'src/runtime/drivers/NativeProviderPolicyValidationV1.h')+'"\n'
    old_admit=verify.admission_source;old_header=verify.cohort_admission_header
    saved={k:os.environ.get(k) for k in ('CPLUS_INCLUDE_PATH','SANITIZE','ASAN_OPTIONS')}
    def with_policy(text):
        body,roles,driver=old_admit(text);return header+body,roles,driver
    try:
        os.environ['CPLUS_INCLUDE_PATH']=str(runtime/'src');verify.admission_source=with_policy
        strict=[]
        for name,blob,provider in [('ui-scene/driver.elf',files['ui-scene/driver.elf'],True),('ebook_reader.elf',app,False)]:
            row=verify.verify(runtime,native_elf,blob,provider=provider);row['path']=name;strict.append(row)
        verify.admission_source=old_admit
        verify.cohort_admission_header=lambda rt,elf:header+old_header(rt,elf)
        cohorts=[]
        for sanitize in ('0','1'):
            os.environ['SANITIZE']=sanitize;os.environ['ASAN_OPTIONS']='detect_leaks=0'
            row=admission.admit_cohort(runtime,native_elf,files,files,app_policy_rows=24)
            row['sanitized']=sanitize=='1';cohorts.append(row)
    finally:
        verify.admission_source=old_admit;verify.cohort_admission_header=old_header
        for k,v in saved.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    require(all(row['elf_count']==37 for row in cohorts),'Incomplete internal cohort admission')
    fs,capacity=pack(files)
    require(read_image(fs,0x510000)==files,'Store readback differs')
    require(admission.unpack_image(fs,a.mkspiffs,0x510000,expected_tool_sha256=sha(a.mkspiffs.read_bytes()))==files,'Independent SPIFFS readback differs')
    require(pack(files)[0]==fs,'Store generation is not deterministic')
    bank=initial_bank_state(firmware,fs,True);pair=parse_record(bank[:96],True)
    require(pair[6]==hashlib.sha256(firmware).digest() and pair[7]==hashlib.sha256(fs).digest(),'Pair SHA/CRC mismatch')
    image=bytearray(raw);image[0x2f0000:0x800000]=fs;image[0xff2000:0xff4000]=bank
    require(image[:0x2f0000]==raw[:0x2f0000] and image[0x800000:0xff2000]==raw[0x800000:0xff2000] and image[0xff4000:]==raw[0xff4000:],'Unexpected changes outside store/pair record')
    name='X4-0.1.74-Reader-Panel-0.1.12-full-0x0.bin';(a.output/name).write_bytes(image)
    (a.output/'bootfs.bin').write_bytes(fs)
    report={'schema':'x4.reader-refresh','version':'0.1.74','source':source,'runtime_source':clean(runtime),
        'baseline_sha256':BASE_SHA,'baseline_receipt_sha256':sha(a.baseline_receipt.read_bytes()),
        'native_elf_sha256':sha(native_elf),'native_firmware_sha256':sha(firmware),'native_unchanged':True,
        'changed_internal_files':sorted(changed),'store_files':digest_inventory(files),'store_generator':capacity,
        'independent_readback_tool_sha256':sha(a.mkspiffs.read_bytes()),
        'panel_version':'0.1.12','panel_sha256':sha(files['panel/driver.elf']),'panel_unchanged':True,
        'strict_admission':strict,'cohort_admission':cohorts,'paired_sha_crc_verified':True,
        'scene_receipt':json.loads((a.scene/'build.json').read_text()),'reader_receipt':json.loads((a.reader/'build.json').read_text()),
        'reader':{'version':'0.1.4','bytes':len(app),'sha256':sha(app),'sd_path':'Apps/ebook-reader/ebook_reader.elf'},
        'image':{'name':name,'bytes':len(image),'sha256':sha(image),'flash_offset':0},
        'hardware_tested':False,'full_flash_overwrites_internal_data':True}
    (a.output/'build-custody.json').write_bytes(encoded(report));print(json.dumps({k:report[k] for k in ('image','reader','store_generator')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('runtime','native','scene','reader','tools','baseline','baseline-receipt','mkspiffs','output'):p.add_argument('--'+n,type=Path,required=True)
    build(p.parse_args())
