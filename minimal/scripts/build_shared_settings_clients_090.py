#!/usr/bin/env python3
"""Rebuild the selected .90 clients, preserving the complete .89 Home profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from compose_shared_settings_090 import require, git
from build_daily_paper_launchers import HEADERS

ROOT = Path(__file__).resolve().parents[2]
READER_PIN = '45cf61ac013fb618e8d7fed63217a35350484d52'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','system','utilities','reader','baseline-store','cc','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in vars(a):setattr(a,name,getattr(a,name).resolve())
    for name in ('runtime','system','utilities','reader'):
        require(not git(getattr(a,name),'status','--porcelain','--untracked-files=normal'),'Clean source required: '+name)
    require(git(a.reader,'rev-parse','HEAD')==READER_PIN,'Canonical SDK source differs')
    require(not a.output.exists(),'Output must be new');a.output.mkdir(parents=True)
    sdk=a.output/'sdk';sdk.mkdir()
    for folder in (a.reader/'sdk/driver',a.runtime/'sdk/app',a.runtime/'sdk/driver',a.runtime/'sdk/hardware',ROOT/'minimal/interfaces'):
        for header in folder.glob('*.h'):shutil.copyfile(header,sdk/header.name)
    for name,digest in HEADERS.items():
        require(hashlib.sha256((sdk/name).read_bytes()).hexdigest()==digest,'Canonical ABI prefix differs: '+name)
    catalog=ROOT/'minimal/sd-app-catalog.json'
    require(len(json.loads(catalog.read_text())['apps'])==24,'Complete app menu missing')
    host=['--desk-clock','--sparse-start','--desk-lock-home','--desk-points-face','--navigation','--alarm-client','--wake-light-restore','--display-rotation','90',
          '--local-sleep-source',ROOT/'minimal/apps/portable_sleep.c','--sleep-capability','x4.power','--sleep-sdk',sdk,'--retained-wake-sdk',a.runtime/'sdk/app',
          '--tagged-alarm-utilities',a.utilities,'--paper-crossfade','--paper-display-sdk',sdk,'--paper-transitions','--quick-actions','--quick-radios','--quick-usb-transfer',
          '--resident-shell-host','--resident-runtime-sdk',a.runtime/'sdk/app','--ble-broadcast','--x4-idle-source',ROOT/'minimal/apps/portable_idle_sleep.c',
          '--x4-idle-sdk',sdk,'--x4-idle-runtime-sdk',a.runtime/'sdk/driver','--contexts-rf-only','--resident-legacy-handoff','--resident-policy',
          '--resident-loading-catalog',catalog,'--raster-snapshot','--frontlight-tone','--frontlight-tone-sdk',sdk,'--display-settled-sdk',sdk,'--crash-report-sd',
          '--boot-animation','--relocation-tools',a.reader/'scripts','--stage-logs','--installed-catalog-volume-instance','9']
    common=['--resident-shell-client','--resident-runtime-sdk',a.runtime/'sdk/app','--alarm-client','--home-app','default.elf',
            '--tagged-alarm-utilities',a.utilities,'--native-time-runtime-repo',a.runtime,'--touch-scrolling','--ble-broadcast','--time-profile','x4-native-time',
            '--resident-policy','--raster-snapshot','--stage-logs']
    spring=common+['--catalog',catalog,'--return-app','default.elf','--paper-crossfade','--paper-display-sdk',sdk,
                   '--installed-catalog-volume-instance','9','--installed-authority-boot',a.baseline_store/'boot.json']
    files=common+['--storage-capability','storage.volume','--storage-instance','9','--file-handlers','--return-app','springboard.elf',
                  '--webdav-sharing','--peer-files','--sharing-export-instance','0','--sharing-tcp-instance','0','--sharing-entropy-instance','0','--sharing-setup-instance','0']
    wifi=common+['--wifi-instance','15','--return-app','springboard.elf','--shared-text-input']
    env=dict(os.environ,NATIVE_APP_CC=str(a.cc),NATIVE_DRIVER_CC=str(a.cc))
    commands=[]
    for name,script,args in [('default','build_paper_clock.py',host),('springboard','build_portable_springboard.py',spring),
                             ('file_browser','build_portable_file_browser.py',files),('wifi_settings','build_portable_wifi.py',wifi),
                             ('installed-apps','build_installed_apps.py',['--runtime-repo',a.runtime])]:
        cmd=list(map(str,[sys.executable,a.system/'scripts'/script,*args,'--output-dir',a.output/name]))
        subprocess.run(cmd,check=True,env=env);commands.append(cmd)
    receipt=dict(sources={name:git(getattr(a,name),'rev-parse','HEAD') for name in ('runtime','system','utilities','reader')},
                 product_source=git(ROOT,'rev-parse','HEAD'),commands=commands,hardware_tested=False)
    (a.output/'client-builds.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt['sources']))

if __name__=='__main__':main()
