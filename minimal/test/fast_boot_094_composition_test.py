#!/usr/bin/env python3
"""Independent .94 flash/store roundtrip and negative custody probes.

Synthetic Home/native payloads are never written as a deliverable.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'minimal/scripts'))
import compose_fast_boot_094 as c
p=argparse.ArgumentParser(description=__doc__)
for n in ('baseline','sd','tools','runtime'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args()
receipt,old,sd,parts,full=c.baseline(a.baseline,a.sd)
build,read_image,initial,parse=c.load_assembly_tools(a.tools,a.runtime)
raw=parts['firmware.bin']+b'SYNTHETIC-NATIVE-NOT-FOR-DELIVERY'
candidate=dict(layout='riscrte-paired-appdata-v2',store_abi=2,firmware_version='0.2.24',
               assets={'firmware.bin':dict(bytes=len(raw),sha256=c.sha(raw))})
artifacts={'default.elf':old['default.elf']+b'SYNTHETIC-HOME-NOT-FOR-DELIVERY',
           'default.json':c.encoded(dict(json.loads(old['default.json']),version=c.HOME))}
new=c.changed_store(old,artifacts,candidate,raw,'1'*40)
image,packing=build(new);state=initial(raw,image,True)
result=bytearray(full)
result[slice(*c.FIRMWARE)]=raw+b'\xff'*(c.FIRMWARE[1]-c.FIRMWARE[0]-len(raw))
result[slice(*c.BOOTFS)],result[slice(*c.BANK_STATE)]=image,state
proof=c.verify(bytes(result),full,old,new,raw,read_image,parse)
count=0

def rejects(fn):
 global count
 try:fn()
 except (ValueError,AssertionError,KeyError):count+=1
 else:raise AssertionError('Negative custody probe accepted')

for at in (0,0x8000,c.FIRMWARE[0],c.FIRMWARE[0]+len(raw)+1,c.FIRMWARE[1],c.BOOTFS[0]+256,c.BANK_STATE[0]+40,c.BANK_STATE[0]+97,0xffffff):
 bad=bytearray(result);bad[at]^=1
 rejects(lambda:c.verify(bytes(bad),full,old,new,raw,read_image,parse))
bad=dict(new,**{'file_browser.elf':new['file_browser.elf']+b'x'})
rejects(lambda:c.verify(bytes(result),full,old,bad,raw,read_image,parse))
bad=dict(new,**{'boot.json':new['boot.json']+b' '})
rejects(lambda:c.verify(bytes(result),full,old,bad,raw,read_image,parse))
rejects(lambda:c.verify(bytes(result),full,old,new,raw+b'x',read_image,parse))
bad=copy.deepcopy(candidate);bad['assets']['firmware.bin']['sha256']='0'*64
rejects(lambda:c.changed_store(old,artifacts,bad,raw,'1'*40))
previous_raw=(a.baseline/'receipts/home-client/build-evidence.json').read_bytes()
assert c.sha(previous_raw)==receipt['home_client']['artifacts']['build-evidence.json']
previous=json.loads(previous_raw)
selected=copy.deepcopy(previous);selected['build_defines'].append('-DPORTABLE_DESK_DEFER_RADIOS')
c.preserve_features(selected,previous)
for key in ('boot_animation','resident_shell','installed_catalog','raster_snapshot','idle_policy','quick_actions'):
 bad=copy.deepcopy(selected);del bad[key]
 rejects(lambda:c.preserve_features(bad,previous))
bad=copy.deepcopy(selected);bad['build_defines'].remove('-DPORTABLE_BOOT_ANIMATION')
rejects(lambda:c.preserve_features(bad,previous))
bad=copy.deepcopy(selected);bad['home_points']['tap_app']='settings.elf'
rejects(lambda:c.preserve_features(bad,previous))
with tempfile.TemporaryDirectory(prefix='x4-094-lock-probe-') as temp:
 root=Path(temp);(root/'minimal').mkdir()
 wanted=root/'minimal/fast-boot-094-inputs.json';wanted.write_text('{"test":"committed"}')
 supplied=root/'supplied.json';supplied.write_bytes(wanted.read_bytes())
 assert c.qualified_lock(supplied,root)[1]=={'test':'committed'}
 supplied.write_text('{"test":"self-qualified-other-source"}')
 rejects(lambda:c.qualified_lock(supplied,root))
assert c.audit_selected_images(json.loads(old['boot.json']),a.baseline/'store',a.sd)==receipt['selected_sd_images']
print(json.dumps(dict(self_test='PASS',negative_checks=count,sd_files=len(sd),selected_sd_images=46,
   native_or_home_execution_tested=False,synthetic_deliverable_created=False,roundtrip=proof),indent=2))
