#!/usr/bin/env python3
"""Build X4 .94 deferred foreground Home from exact clean source inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from compose_shared_settings_090 import require, git, sha
from build_daily_paper_launchers import HEADERS

ROOT = Path(__file__).resolve().parents[2]
READER_PIN = '45cf61ac013fb618e8d7fed63217a35350484d52'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','system','utilities','reader','baseline-store','cc','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runtime-revision',required=True)
    p.add_argument('--system-revision',required=True)
    a=p.parse_args()
    for name in vars(a):
        if isinstance(getattr(a,name),Path):setattr(a,name,getattr(a,name).resolve())
    for name in ('runtime','system','utilities','reader'):
        require(not git(getattr(a,name),'status','--porcelain','--untracked-files=normal'),'Clean source required: '+name)
    require(git(a.reader,'rev-parse','HEAD')==READER_PIN,'Canonical SDK source differs')
    require(not a.output.exists(),'Output must be new');a.output.mkdir(parents=True)
    sdk=a.output/'sdk';sdk.mkdir()
    for folder in (a.reader/'sdk/driver',a.runtime/'sdk/app',a.runtime/'sdk/driver',a.runtime/'sdk/hardware',ROOT/'minimal/interfaces'):
        for header in folder.glob('*.h'):shutil.copyfile(header,sdk/header.name)
    for name,digest in HEADERS.items():
        require(hashlib.sha256((sdk/name).read_bytes()).hexdigest()==digest,'Canonical ABI prefix differs: '+name)
    require(git(a.system,'rev-parse','HEAD')==a.system_revision,'Wrong requested System source')
    require(git(a.runtime,'rev-parse','HEAD')==a.runtime_revision,'Wrong requested Runtime source')
    require(git(a.utilities,'rev-parse','HEAD')=='fc0bdbbbc600ce891e60c44d091fce0586ade7d8','Wrong delivered Utilities source')
    require(not git(ROOT,'status','--porcelain','--untracked-files=normal'),'Clean product source required')
    catalog=ROOT/'minimal/sd-app-catalog.json'
    require(len(json.loads(catalog.read_text())['apps'])==24,'Complete app menu missing')
    host=['--desk-clock','--sparse-start','--desk-lock-home','--desk-points-face','--navigation','--alarm-client','--wake-light-restore','--display-rotation','90',
          '--local-sleep-source',ROOT/'minimal/apps/portable_sleep.c','--sleep-capability','x4.power','--sleep-sdk',sdk,'--retained-wake-sdk',a.runtime/'sdk/app',
          '--tagged-alarm-utilities',a.utilities,'--paper-crossfade','--paper-display-sdk',sdk,'--paper-transitions','--quick-actions','--quick-radios','--quick-usb-transfer',
          '--resident-shell-host','--resident-runtime-sdk',a.runtime/'sdk/app','--ble-broadcast','--x4-idle-source',ROOT/'minimal/apps/portable_idle_sleep.c',
          '--x4-idle-sdk',sdk,'--x4-idle-runtime-sdk',a.runtime/'sdk/driver','--contexts-rf-only','--resident-legacy-handoff','--resident-policy',
          '--resident-loading-catalog',catalog,'--raster-snapshot','--frontlight-tone','--frontlight-tone-sdk',sdk,'--display-settled-sdk',sdk,'--crash-report-sd',
          '--boot-animation','--relocation-tools',a.reader/'scripts','--stage-logs','--installed-catalog-volume-instance','9','--deferred-foreground-services']
    env=dict(os.environ,NATIVE_APP_CC=str(a.cc),NATIVE_DRIVER_CC=str(a.cc))
    target=a.output/'default'
    cmd=list(map(str,[sys.executable,a.system/'scripts/build_paper_clock.py',*host,'--output-dir',target]))
    subprocess.run(cmd,check=True,env=env)
    manifest=json.loads((target/'default.json').read_text())
    old=json.loads((a.baseline_store/'default.json').read_text())
    require(old['version']=='0.4.12' and manifest==dict(old,version='0.4.13'),'Delivered Home profile/authority differs')
    record=json.loads((target/'build-evidence.json').read_text())
    require(record['version']=='0.4.13' and record['working_tree_dirty'] is False,'Unqualified shared Home build')
    require(record.get('deferred_foreground_services') is True,'Deferred service profile missing')
    # The .93 product sleep hook must remain byte-identical.
    require(sha(ROOT/'minimal/apps/portable_sleep.c')=='0858a85e56bb12ef1255b02eeb5fb3618a4e46fd283e0a369f4f3bffefe0462b','Minute SD-close hook changed')
    record['upstream_profile_version']='0.4.13'
    record['x4_product']={'commit':git(ROOT,'rev-parse','HEAD'),'dirty':False,
      'base':'489485d9ca597e88aa94e0379c6f1d860a3e5c47','version':'0.1.94',
      'timer_storage_transaction':{'capability':'storage.volume','instance':9,'prepare_commit':True,'checked_resume':True},
      'recipe_sha256':sha(Path(__file__)),'command':cmd}
    record['hardware_tested']=False
    (target/'default.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (target/'build-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'version':manifest['version'],'elf_sha256':sha(target/'default.elf'),'product':record['x4_product']['commit']}))

if __name__=='__main__':main()
