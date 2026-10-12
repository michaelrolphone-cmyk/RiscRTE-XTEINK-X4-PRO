#!/usr/bin/env python3
"""Pinned Files payload, flash preservation and fail-closed composition probes."""
import argparse
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_mounted_files_097_final as c

p=argparse.ArgumentParser()
for n in ('baseline','files','system-source','tools','runtime-source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();lock=c.load_lock();base,old,sd,parts,full=c.baseline(a.baseline,lock)
artifacts={n:(a.files/n).read_bytes() for n in c.FILES_NAMES}
record=c.validate_files(artifacts,a.system_source,old,lock)
new=c.payload(old,sd,artifacts,'a'*40,base['sd_lifecycle'])
rejected=[]
def reject(name,fn):
    try:fn()
    except (ValueError,AssertionError,KeyError):rejected.append(name);return
    raise AssertionError('Accepted '+name)
for name in artifacts:
    bad=dict(artifacts);bad[name]+=b'x'
    reject('unbound-artifact-'+name,lambda:c.validate_files(bad,a.system_source,old,lock))
for key in lock['profile_invariants']:
    bad=dict(artifacts);r=copy.deepcopy(record);r[key]=None;bad['file_browser-build-record.json']=c.encoded(r)
    relocked=copy.deepcopy(lock);relocked['files_artifacts']=c.inventory(bad)
    reject('profile-change-'+key,lambda:c.validate_files(bad,a.system_source,old,relocked))
for name in old:
    if name in c.ALLOWED:continue
    bad=dict(new);bad[name]+=b'x'
    reject('unrelated-store-'+name,lambda:c.verify_payload(old,bad,sd,sd,artifacts,'a'*40,base['sd_lifecycle']))
for name in sd:
    bad=dict(sd);bad[name]+=b'x'
    reject('unrelated-sd-'+name,lambda:c.verify_payload(old,new,sd,bad,artifacts,'a'*40,base['sd_lifecycle']))
bad=dict(new);cohort=json.loads(bad['cohort.json']);cohort['firmware_sha256']='0'*64;bad['cohort.json']=c.encoded(cohort)
reject('native-cohort-identity',lambda:c.verify_payload(old,bad,sd,sd,artifacts,'a'*40,base['sd_lifecycle']))
for name in ('file_browser.elf','file_browser.json'):
    bad=dict(new);bad[name]+=b'x'
    reject('changed-payload-'+name,lambda:c.verify_payload(old,bad,sd,sd,artifacts,'a'*40,base['sd_lifecycle']))
build,read_image,initial,parse=c.load_assembly_tools(a.tools,a.runtime_source)
image,packing=c.ordered_build(new,build)
same,same_record=c.ordered_build(dict(reversed(list(new.items()))),build)
assert image==same and packing==same_record and packing['empty_blocks']>=2
result=bytearray(full);result[slice(*c.BOOTFS)]=image
result[slice(*c.BANK_STATE)]=initial(parts['firmware.bin'],image,True)
c.verify_image(bytes(result),full,old,new,read_image,parse,parts['firmware.bin'])
for off in (0,0x8000,0x10000,0x26ffff,0x270000,0x800000,0xff0000,0xff4000,0xffffff,c.BOOTFS[0],c.BANK_STATE[0]+15,c.BANK_STATE[0]+96):
    bad=bytearray(result);bad[off]^=1
    reject('flash-mutation-'+hex(off),lambda:c.verify_image(bytes(bad),full,old,new,read_image,parse,parts['firmware.bin']))
assert len(old)-len(c.ALLOWED)==100 and len(sd)==81 and len(base['sd_lifecycle'])==13
# Final image naming requires exact, read-back product publication evidence.
import tempfile
reject('missing-final-publication',lambda:c.publication(None,'a'*40,'b'*40,False))
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'publication.json'
    proof=dict(repository='michaelrolphone-cmyk/RiskRTE-XTEINK-X4-PRO',commit='a'*40,
               tree='b'*40,branch='feat/x4-mounted-files-097-20261012',
               readback_verified=True,readback_verified_at='2026-10-12T04:00:00Z')
    path.write_bytes(c.encoded(proof))
    assert c.publication(path,'a'*40,'b'*40,False)==proof
    reject('preflight-publication-claim',lambda:c.publication(path,'a'*40,'b'*40,True))
    for key,value in (('repository','other/repo'),('commit','0'*40),('tree','0'*40),
                      ('branch','other'),('readback_verified',False),('readback_verified_at','')):
        bad=dict(proof);bad[key]=value;path.write_bytes(c.encoded(bad))
        reject('wrong-publication-'+key,lambda:c.publication(path,'a'*40,'b'*40,False))
print(json.dumps(dict(passed=True,negative_probes=len(rejected),rejected=rejected,
    source_hashes_verified=len(record['source_sha256']),preserved_store_files=100,
    preserved_sd_files=81,grant_count=record['grant_count'],deterministic_packing=True,
    empty_blocks=packing['empty_blocks'],occupied_blocks=packing['occupied_blocks'],
    boot_order_unchanged=True,final_published_system_rebuild=True,hardware_tested=False),indent=2))
