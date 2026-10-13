#!/usr/bin/env python3
"""Exercise selected .111 settings source without changing or flashing firmware."""
import argparse, hashlib, json, os, pathlib, subprocess, sys
p=argparse.ArgumentParser()
for n in ('runtime','system','output'): p.add_argument('--'+n,type=pathlib.Path,required=True)
p.add_argument('--sanitize',action='store_true');a=p.parse_args()
a.runtime=a.runtime.resolve();a.system=a.system.resolve();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
pins={'runtime':'a91edf3fada6a559ec107186dd163d0c8da10d29','system':'1db9915d53abf13e163596838adaac5647879e58'}
for n,pin in pins.items():
 root=getattr(a,n)
 assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==pin
 assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True).strip()
env=dict(os.environ,SYSTEM_ROOT=str(a.system),SANITIZE=str(int(a.sanitize)),SANITIZERS='undefined',ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
records=[]
def run(name,command,cwd):
 log=a.output/(name+'.log')
 with log.open('w') as f: result=subprocess.run(list(map(str,command)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
 records.append(dict(name=name,command=list(map(str,command)),return_code=result.returncode,log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
 (a.output/'results.json').write_text(json.dumps(dict(pins=pins,sanitized=a.sanitize,records=records,hardware_tested=False),indent=2)+'\n')
 print(name,'PASS' if result.returncode==0 else 'FAIL',flush=True)
 if result.returncode: print(log.read_text()[-6000:]);raise SystemExit(result.returncode)
for name in ('native_replica_core','native_replica_sd','native_replica_sd_reader','native_checked_sd_restore','native_checked_sd_restore_power','native_first_sd_checked_store','native_atomic_checked_store','native_atomic_wifi_bridge','native_settings_availability','atomic_key_value_cohort'):
 run(name,['bash',a.runtime/'test'/('run_'+name+'_test.sh')],a.runtime)
for name in ('wifi_atomic','wifi_availability'):
 cmd=[sys.executable,a.system/'scripts'/('test_'+name+'.py'),'--output',a.output/name]
 if a.sanitize:cmd+=['--sanitize']
 if name=='wifi_availability':cmd+=['--paper']
 run(name,cmd,a.system)
