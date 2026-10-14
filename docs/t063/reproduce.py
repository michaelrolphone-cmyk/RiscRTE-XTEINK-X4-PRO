#!/usr/bin/env python3
"""Reproduce T063 host checks. Does not build, package or flash firmware."""
import argparse,json,os,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('x4','wave','watch','utilities','settings','system','runtime','desk-sdk','output'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
for k,v in vars(a).items():setattr(a,k,v.resolve())
def run(cmd,log,env=None):
    with (out/log).open('w') as f:
        subprocess.run([str(v) for v in cmd],stdout=f,stderr=subprocess.STDOUT,env=env,check=True)
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    # Preserve sanitizer coverage on Darwin without the Linux-only linker flag.
    wrapper=tmp/'cc-ubsan'
    wrapper.write_text("#!/usr/bin/env python3\nimport os,sys\na=[('-fsanitize=undefined' if x=='-fsanitize=address,undefined' else x) for x in sys.argv[1:] if x!='-no-pie']\nos.execvp('cc',['cc',*a])\n")
    wrapper.chmod(0o755)
    env={**os.environ,'CC':str(wrapper)}
    run(['python3',a.utilities/'scripts/test_alarm_first_attempt.py','--runtime',a.runtime,'--system-apps',a.system,'--output',out/'alarm'],'alarm.log',env)
    log=out/'alarm.log';log.write_text(log.read_text().replace('normal and ASan/UBSan','normal and UBSan (wrapper; ASan not run)'))
    script=(a.x4/'minimal/test/run_sparse_desk_clock_sleep_test.sh').read_text()
    # Bash 3 errors on a declared empty array with nounset. No test cases change.
    script=script.replace('set -euo pipefail','set -eo pipefail').replace('root="$(cd "$(dirname "$0")/../.." && pwd)"','root='+__import__('shlex').quote(str(a.x4)))
    local=tmp/'sleep.sh';local.write_text(script)
    run(['bash',local],'x4-sleep.log',{**env,'RISCRTE_RUNTIME_ROOT':str(a.runtime),'RISCRTE_APPS_ROOT':str(a.system),'RISCRTE_DESK_SDK_ROOT':str(a.desk_sdk),'SANITIZE':'1','SANITIZERS':'undefined'})
    for mode,flags in [('normal',[]),('ubsan',['-fsanitize=undefined','-fno-sanitize-recover=all'])]:
        for name in ['test_vendor_panel','test_rtc','settings']:
            exe=out/(name+'-'+mode)
            if name=='settings':
                includes=[a.settings/'lib/PortableApps/include',a.settings/'lib/NativeApps/include']
                sources=[a.settings/'Apps/settings.c',a.settings/'test/native_apps/settings_clock_change_test.c']
            else:
                includes=[a.wave/'include',a.watch/'sdk/driver',a.watch/'sdk/app',a.watch/'include']
                sources=[a.wave/'tests'/(name+'.c')]
            run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*flags,*['-I'+str(i) for i in includes],*sources,'-o',exe],name+'-'+mode+'-compile.log')
            run([exe],name+'-'+mode+'.log')
print('T063 host checks PASS: normal/UBSan; X4 sleep UBSan. Hardware not tested.')
