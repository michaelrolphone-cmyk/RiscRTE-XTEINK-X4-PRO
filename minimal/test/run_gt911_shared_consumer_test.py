#!/usr/bin/env python3
"""Qualify production GT911 to exact shared reducer; host simulation only."""
import argparse, hashlib, json, os, shlex, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--sdk',required=True,type=Path)
p.add_argument('--system',required=True,type=Path)
p.add_argument('--driver',type=Path)
p.add_argument('--output',required=True,type=Path)
p.add_argument('--sanitize',action='store_true')
p.add_argument('--check-ordering-mutation',action='store_true')
a=p.parse_args(); root=Path(__file__).resolve().parents[2]
sdk=a.sdk.resolve(); system=a.system.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
shared=system/'lib/PortableApps/include'; driver=(a.driver or root/'minimal/drivers/x4pro_gt911/driver.c').resolve()
assert (sdk/'RiscTouchV1.h').read_bytes()==(shared/'RiscTouchV1.h').read_bytes(), 'Touch ABI copies differ'
flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-pedantic']
if a.sanitize: flags+=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
cc=os.environ.get('CC','cc'); objects=[]; commands=[]
for source,include in [(root/'minimal/test/gt911_shared_consumer_backend.c',sdk),(driver,sdk),(root/'minimal/test/gt911_shared_consumer_test.c',shared)]:
 obj=out/(source.stem+'.o'); cmd=[cc,*flags,'-MMD','-MF',str(obj.with_suffix('.d')),'-I'+str(include),'-c',str(source),'-o',str(obj)]
 subprocess.run(cmd,check=True); commands.append(cmd); objects.append(obj)
exe=out/'test'; cmd=[cc,*flags,*map(str,objects),'-o',str(exe)]; subprocess.run(cmd,check=True); commands.append(cmd)
scenes=['contact-before-motion','queued-independent-tap','same-timestamp-edges','gap-and-ack']
for scene in scenes:
 cmd=[str(exe),scene]; subprocess.run(cmd,check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0')); commands.append(cmd)
files={Path(__file__).resolve()}
for obj in objects:
 dep=obj.with_suffix('.d').read_text().replace('\\\n',' ')
 files.update(Path(name) for name in shlex.split(dep.split(':',1)[1]))
files=sorted(files)
receipt={'hardware_tested':False,'sanitized':a.sanitize,'scenes':scenes,'commands':commands,'source_sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if a.check_ordering_mutation:
 assert not a.driver, 'Mutation control requires the unchanged product provider'
 source=driver.read_text()
 marker='    for (uint8_t i = 0; i < contacts; ++i) {\n        const risc_touch_contact_v1 *contact = &current[i];'
 first=source.index(marker,source.index('/* Publish additions before'))
 second=source.index(marker,first+len(marker)); end=source.index('    if (home != was_home)',second)
 mutation=out/'ordering-mutation'; (mutation/'x4pro_gt911').mkdir(parents=True,exist_ok=True)
 (mutation/'x4pro_board_power').mkdir(exist_ok=True)
 mutated=mutation/'x4pro_gt911/driver.c'
 mutated.write_text(source[:first]+source[second:end]+source[first:second]+source[end:])
 (mutation/'x4pro_board_power/PowerReadyV1.h').write_bytes((driver.parent.parent/'x4pro_board_power/PowerReadyV1.h').read_bytes())
 command=[sys.executable,str(Path(__file__).resolve()),'--sdk',str(sdk),'--system',str(system),'--driver',str(mutated),'--output',str(mutation/'build')]
 result=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (mutation/'rejected.log').write_text(result.stdout)
 assert (mutation/'build/test').is_file(), result.stdout
 assert result.returncode!=0 and 's.cancelled' in result.stdout, result.stdout
 control={'mutation':'Retained MOVE phase before new DOWN phase','expected_rejection':True,'command':command,'returncode':result.returncode,'assertion':'s.cancelled','production_source_unchanged':hashlib.sha256(driver.read_bytes()).hexdigest()==receipt['source_sha256'][str(driver)]}
 assert control['production_source_unchanged']
 (mutation/'receipt.json').write_text(json.dumps(control,indent=2)+'\n')
 print('GT911 shared consumer PASS: reordered-report mutation rejected')
