#!/usr/bin/env python3
"""Profile production file-transfer boundaries; physical transport is simulated."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
for name in ('reader','runtime','drivers','tinyusb','output'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--ubsan',action='store_true');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
subprocess.run([sys.executable,a.reader/'scripts/prepare_usb_device_stack.py','--source',a.tinyusb,'--output',out/'stack'],check=True)
subprocess.run([sys.executable,ROOT/'minimal/scripts/prepare_sdk.py','--reader',a.reader,'--runtime',a.runtime,'--output',out/'sdk'],check=True)
# The historical wire fixture names the pre-split shared helper by relative path.
# Redirect that test-only include to the exact selected StorageFatFs helper.
board=out/'fixture-board';board.mkdir()
proto=(a.reader/'Drivers/x4pro_board/x4pro_proto.h').read_text()
assert proto.count('#include "../storage_fatfs/sd_protocol.h"')==1
(board/'x4pro_proto.h').write_text(proto.replace('#include "../storage_fatfs/sd_protocol.h"','#include <sd_protocol.h>'))
sources=[ROOT/'minimal/test/usb_bulk_profile_test.c',a.reader/'test/usb_device_msc/sd_directory_bridge.c',a.reader/'Drivers/usb_device_msc_esp32s3/driver.c',a.reader/'Drivers/usb_device_msc_esp32s3/StackDefaults.c',a.drivers/'lib/StorageFatFs/fatfs/ff.c',a.drivers/'lib/StorageFatFs/fatfs/ffunicode.c']+[out/'stack'/n for n in ('tusb.c','common/tusb_fifo.c','device/usbd.c','device/usbd_control.c','class/msc/msc_device.c')]
inc=[board,out/'sdk',ROOT/'minimal/test',a.reader/'Drivers/usb_device_msc_esp32s3',out/'stack',a.drivers/'lib/StorageFatFs',a.reader/'Drivers/x4pro_board',a.reader]
sanitize=['-fsanitize=undefined','-fno-sanitize=alignment','-fno-sanitize-recover=all'] if a.ubsan else []
flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-overflow',*sanitize,'-DUSB_OWNER_TEST_SOURCE="'+str(a.reader/'test/usb_device_msc/owner_test.c')+'"']+['-I'+str(i) for i in inc]
if sys.platform=='darwin':flags+=['-ffunction-sections','-fdata-sections']
commands=[];objects=[];deps={}
for i,source in enumerate(sources):
 obj=out/(str(i)+'.o');dep=out/(str(i)+'.d');cmd=[os.getenv('CC','cc'),*flags,'-MMD','-MF',str(dep),'-c',str(source),'-o',str(obj)]
 subprocess.run(cmd,check=True);commands.append(cmd);objects.append(obj)
 for n in dep.read_text().replace('\\\n',' ').split(':',1)[1].split():q=Path(n).resolve();deps[str(q)]=hashlib.sha256(q.read_bytes()).hexdigest()
cmd=[os.getenv('CC','cc'),*sanitize,*map(str,objects),*(['-Wl,-dead_strip'] if sys.platform=='darwin' else []),'-o',str(out/'profile')];subprocess.run(cmd,check=True);commands.append(cmd)
r=subprocess.run([out/'profile'],check=True,capture_output=True,text=True,timeout=60);print(r.stdout,end='');print(r.stderr,end='',file=sys.stderr)
row=json.loads(r.stdout.splitlines()[-1]);record={'result':row,'ubsan':a.ubsan,'alignment_check':False if a.ubsan else None,'source_sha256':deps,'commands':commands,'limits':'Counts from actual provider/TinyUSB/SD/FatFs. USB DCD and physical SDMMC/GPIO/clock are simulated; no hardware elapsed rate inferred. Only print after cleanup.'}
record['source_commits']={name:subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip() for name,path in [('x4',ROOT),('reader',a.reader),('runtime',a.runtime),('drivers',a.drivers),('tinyusb',a.tinyusb)]}
record['fixture_proto_input_sha256']=hashlib.sha256((a.reader/'Drivers/x4pro_board/x4pro_proto.h').read_bytes()).hexdigest()
(out/'profile.json').write_text(json.dumps(record,indent=2)+'\n')
