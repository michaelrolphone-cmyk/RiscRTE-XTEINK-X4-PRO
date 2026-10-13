import sys,os,subprocess,json
from pathlib import Path
r=Path('/mnt/data/x4fix');system=r/'system-source';x4=r/'x4-source';rt=r/'x4-runtime-source';sdk=r/'sdk'
wrapper=r/'ccbin/xtensa-esp32s3-elf-gcc';wrapper.parent.mkdir(exist_ok=True);wrapper.write_text('#!/bin/sh\nexec '+str(r/'xtensa-toolchain/bin/xtensa-esp32s3-elf-gcc')+' -DPORTABLE_ALARM_BUSY_DEFER "$@"\n');wrapper.chmod(0o755)
for tool in ['nm','objdump','readelf']:
 p=wrapper.parent/('xtensa-esp32s3-elf-'+tool)
 if not p.exists():p.symlink_to(r/('xtensa-toolchain/bin/xtensa-esp32s3-elf-'+tool))
host=['--desk-clock','--sparse-start','--desk-lock-home','--desk-points-face','--navigation','--alarm-client','--wake-light-restore','--display-rotation','90',
 '--local-sleep-source',x4/'minimal/apps/portable_sleep.c','--sleep-capability','x4.power','--sleep-sdk',sdk,'--retained-wake-sdk',rt/'sdk/app',
 '--tagged-alarm-utilities',r/'utilities-source-with-git','--paper-crossfade','--paper-display-sdk',sdk,'--paper-transitions','--quick-actions','--quick-radios','--quick-usb-transfer',
 '--resident-shell-host','--resident-runtime-sdk',rt/'sdk/app','--ble-broadcast','--x4-idle-source',x4/'minimal/apps/portable_idle_sleep.c',
 '--x4-idle-sdk',sdk,'--x4-idle-runtime-sdk',rt/'sdk/driver','--contexts-rf-only','--resident-legacy-handoff','--resident-policy',
 '--resident-loading-catalog',x4/'minimal/sd-app-catalog.json','--raster-snapshot','--frontlight-tone','--frontlight-tone-sdk',sdk,'--display-settled-sdk',sdk,'--crash-report-sd',
 '--boot-animation','--relocation-tools',r/'reader-sdk/scripts','--stage-logs','--installed-catalog-volume-instance','9','--deferred-foreground-services',
 '--experimental-atomic-quick','--experimental-atomic-home-automatic','--experimental-settings-availability']
cmd=list(map(str,[sys.executable,system/'scripts/build_paper_clock.py',*host,'--output-dir',r/sys.argv[1]]))
(r/(sys.argv[1]+'-command.json')).write_text(json.dumps({'command':cmd,'compiler':str(wrapper),'extra_define':'PORTABLE_ALARM_BUSY_DEFER','source_archive_sha':'a3504d4f8f342d9d78383978e8b70032d0097c23'},indent=2))
subprocess.run(cmd,check=True,env=dict(os.environ,NATIVE_APP_CC=str(wrapper)))
