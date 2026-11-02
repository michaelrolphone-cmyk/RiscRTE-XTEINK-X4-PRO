#!/usr/bin/env python3
"""Build/test provider-owned X4 standard power bridges with exact public SDKs."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('runtime','reader','watch','system','utilities','output'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--compiler',type=Path)
a=p.parse_args();root=Path(__file__).resolve().parents[2];out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
canonical=out/'canonical';sdk=out/'include';sdk.mkdir(exist_ok=True)
subprocess.run([sys.executable,str(root/'minimal/scripts/prepare_sdk.py'),'--runtime',str(a.runtime),'--reader',str(a.reader),'--output',str(canonical)],check=True)
shutil.copytree(a.system/'lib/PortableApps/include',sdk,dirs_exist_ok=True)
shutil.copytree(a.system/'lib/PortableApps/time',out/'time',dirs_exist_ok=True)
for path in (a.utilities/'lib/Alarm/include').glob('*.h'):shutil.copyfile(path,sdk/path.name)
for path in canonical.glob('*.h'):shutil.copyfile(path,sdk/path.name)
for name in ('RiscDisplayPowerV1.h','RiscPowerSleepV1.h'):
 source=a.watch/'sdk/driver'/name
 if (sdk/name).exists():assert (sdk/name).read_bytes()==source.read_bytes(),name
 else:shutil.copyfile(source,sdk/name)
sources=[root/'minimal/drivers'/name/'driver.c' for name in ('x4pro_home_power','x4pro_home_display_power')]
cases='happy missing-binding enrolled-unavailable held-key key-retained clock-backwards light-read light-off panel-refused panel-retained panel-unknown storage-prepare storage-commit media-unavailable storage-retained panel-restore light-restore native-retained native-zero native-unknown'.split()
runs=[]
for mode in ('normal','sanitized'):
 directory=out/mode;directory.mkdir(exist_ok=True)
 flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DPORTABLE_DESK_POINTS_FACE','-DPORTABLE_DESK_POINTS_SNAPSHOT','-I'+str(sdk)]
 if mode=='sanitized':flags+=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie']
 objects=[]
 for source,symbol in zip(sources,('x4_home_power_get','x4_home_display_get')):
  obj=directory/(source.parent.name+'.o');subprocess.run(['cc',*flags,'-Dt5_driver_get='+symbol,'-c',str(source),'-o',str(obj)],check=True);objects.append(obj)
 binary=directory/'test';subprocess.run(['cc',*flags,str(root/'minimal/test/shared_home_power_test.c'),*map(str,objects),'-o',str(binary)],check=True)
 for case in cases:
  result=subprocess.run([str(binary),case],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
  (directory/(case+'.log')).write_text(result.stdout+result.stderr)
  if result.returncode:print(result.stdout+result.stderr);result.check_returncode()
  print(result.stdout,end='');runs.append({'mode':mode,'case':case,'output':result.stdout})
products=[]
if a.compiler:
 cc=str(a.compiler.resolve());tools=cc.removesuffix('gcc')
 for source in sources:
  directory=out/'target'/source.parent.name;directory.mkdir(parents=True,exist_ok=True);elf=directory/'driver.elf'
  command=[cc,'-std=c11','-O2','-fno-ivopts','-fPIC','-mtext-section-literals','-mlongcalls','-fvisibility=hidden','-fno-builtin','-nostdlib','-nostartfiles','-shared','-Wall','-Wextra','-Werror','-I'+str(sdk),'-Wl,--hash-style=sysv','-Wl,--exclude-libs,ALL','-Wl,--no-relax',str(source),'-lgcc','-o',str(elf)]
  subprocess.run(command,check=True)
  for name in ('normalize_xtensa_relocations.py','validate_xtensa_relative_targets.py'):subprocess.run([sys.executable,str(a.reader/'scripts'/name),str(elf)],check=True)
  rows=[x.split() for x in subprocess.check_output([tools+'readelf','--dyn-syms','--wide',str(elf)],text=True).splitlines()]
  imports={r[7] for r in rows if len(r)>=8 and r[4]=='GLOBAL' and r[6]=='UND'};exports={r[7] for r in rows if len(r)>=8 and r[4]=='GLOBAL' and r[6]!='UND' and r[3]=='FUNC'}
  assert imports<={'strcmp','memcpy','memset'} and exports=={'t5_driver_get'},(imports,exports)
  assert 's32c1i' not in subprocess.check_output([tools+'objdump','-d',str(elf)],text=True).lower()
  shutil.copyfile(source.parent/'manifest.json',directory/'manifest.json')
  products.append({'id':source.parent.name,'sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'bytes':elf.stat().st_size,'imports':sorted(imports),'command':command})
files=[*sources,*[s.parent/'manifest.json' for s in sources],root/'minimal/test/shared_home_power_test.c',Path(__file__)]
(out/'receipt.json').write_text(json.dumps({'source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'runs':runs,'products':products,'physical_hardware_tested':False,'sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'sdk_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sdk.glob('*.h')}},indent=2)+'\n')
