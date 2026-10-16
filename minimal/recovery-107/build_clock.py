#!/usr/bin/env python3
"""Build cumulative X4 Home using the recovered .105/.106 feature selection."""
import argparse,sys,os,subprocess,json,hashlib,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ('system','x4','runtime','sdk','utilities','reader-scripts','compiler','output'):
 p.add_argument('--'+n,required=True,type=Path)
a=p.parse_args()
for n in vars(a):setattr(a,n,getattr(a,n).resolve())
system=a.system;x4=a.x4;rt=a.runtime;sdk=a.sdk;r=a.output
r.mkdir(parents=True,exist_ok=True)
shutil.copytree(a.sdk,r/'sdk',dirs_exist_ok=True)
shutil.copytree(x4/'minimal/interfaces',r/'sdk',dirs_exist_ok=True)
sdk=r/'sdk'
wrapper=r/'ccbin/xtensa-esp32s3-elf-gcc';wrapper.parent.mkdir(exist_ok=True)
import shlex
wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(a.compiler))+' -DPORTABLE_ALARM_BUSY_DEFER "$@"\n');wrapper.chmod(0o755)
for tool in ('nm','objdump','readelf'):
 target=wrapper.parent/('xtensa-esp32s3-elf-'+tool)
 if not target.exists():target.symlink_to(a.compiler.parent/target.name)
assert hashlib.sha256((x4/'minimal/apps/portable_sleep.c').read_bytes()).hexdigest()=='0858a85e56bb12ef1255b02eeb5fb3618a4e46fd283e0a369f4f3bffefe0462b'
host=['--desk-clock','--sparse-start','--desk-lock-home','--desk-points-face','--navigation','--alarm-client','--wake-light-restore','--display-rotation','90',
 '--local-sleep-source',x4/'minimal/apps/portable_sleep.c','--sleep-capability','x4.power','--sleep-sdk',sdk,'--retained-wake-sdk',rt/'sdk/app',
 '--tagged-alarm-utilities',a.utilities,'--paper-crossfade','--paper-display-sdk',sdk,'--paper-transitions','--quick-actions','--quick-radios','--quick-usb-transfer',
 '--resident-shell-host','--resident-runtime-sdk',rt/'sdk/app','--ble-broadcast','--x4-idle-source',x4/'minimal/apps/portable_idle_sleep.c',
 '--x4-idle-sdk',sdk,'--x4-idle-runtime-sdk',rt/'sdk/driver','--contexts-rf-only','--resident-legacy-handoff','--resident-policy',
 '--resident-loading-catalog',x4/'minimal/sd-app-catalog.json','--raster-snapshot','--frontlight-tone','--frontlight-tone-sdk',sdk,'--display-settled-sdk',sdk,'--crash-report-sd',
 '--boot-animation','--relocation-tools',a.reader_scripts,'--stage-logs','--installed-catalog-volume-instance','9','--deferred-foreground-services',
 '--experimental-atomic-quick','--experimental-atomic-home-automatic','--experimental-settings-availability']
cmd=list(map(str,[sys.executable,system/'scripts/build_paper_clock.py',*host,'--output-dir',r/'home']))
(r/'command.json').write_text(json.dumps({'command':cmd,'extra_define':'PORTABLE_ALARM_BUSY_DEFER'},indent=2)+'\n')
subprocess.run(cmd,check=True,env=dict(os.environ,NATIVE_APP_CC=str(wrapper)))
# The compiler wrapper contributes to the actual target profile. Keep it in
# the downstream evidence consumed by host-composition qualification as well.
evidence_path=r/'home/build-evidence.json'
evidence=json.loads(evidence_path.read_text())
extra='-DPORTABLE_ALARM_BUSY_DEFER'
if extra not in evidence['build_defines']:evidence['build_defines'].append(extra)
evidence['compiler_wrapper_defines']=[extra]
evidence_path.write_text(json.dumps(evidence,indent=2)+'\n')
