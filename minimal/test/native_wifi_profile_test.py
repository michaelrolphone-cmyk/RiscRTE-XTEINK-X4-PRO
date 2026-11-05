#!/usr/bin/env python3
"""Source-bound X4 successor profile and focused Runtime admission; no deployment."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PIN='532c502fb2aad358d46166d5fd1df8358148f20e'
def run(cmd,log):
    p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    log.write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('Command failed: '+str(log))
    return p.stdout
def configure(runtime,profile,out):
    source=out/'source';source.mkdir(parents=True)
    (source/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.22)\nproject(x4_wifi_contract NONE)\ninclude("'+str(runtime/'idf/product-profile.cmake')+'")\nfile(WRITE "${CMAKE_BINARY_DIR}/profile.txt" "definitions=${RISC_NATIVE_DEFINITIONS}\\nsettings=${RISC_NATIVE_SETTINGS_HEADER}\\npartitions=${RISC_NATIVE_PARTITIONS}\\nlinks=${RISC_NATIVE_LINK_OPTIONS}\\n")\n')
    build=out/'build'
    run(['cmake','-S',source,'-B',build,'-DRISC_PRODUCT_PROFILE='+str(profile)],out/'configure.log')
    return dict(l.split('=',1) for l in (build/'profile.txt').read_text().splitlines())
def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.runtime=a.runtime.resolve();a.output=a.output.resolve()
    assert not a.output.exists();a.output.mkdir(parents=True)
    assert subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD'],text=True).strip()==PIN
    subprocess.run(['git','-C',str(a.runtime),'diff','--exit-code','HEAD','--'],check=True)
    old=configure(a.runtime,ROOT/'profiles/native-provision-123.cmake',a.output/'previous')
    new=configure(a.runtime,ROOT/'profiles/native-wifi.cmake',a.output/'successor')
    before=set(old['definitions'].split(';'));after=set(new['definitions'].split(';'))
    assert after==before|{'RISC_RUNTIME_PREFERENCE_STORE=1'}
    assert old['partitions']==new['partitions'] and old['links']==new['links']
    header=ROOT/'profiles/native-wifi-settings.h';assert Path(new['settings'])==header
    assert 'RISC_RUNTIME_ATOMIC_KEY_VALUE=1' in after
    # Compile only the selected broker features needed by this focused fixture.
    # Full product firmware still needs separate IDF link/resource qualification.
    selected=['-D'+d for d in sorted(after) if d.split('=',1)[0] in {'RISC_RUNTIME_ATOMIC_KEY_VALUE','RISC_RUNTIME_PREFERENCE_STORE'}]
    sources=['src/bootstrap/Json.cpp','src/bootstrap/Board.cpp','src/bootstrap/Runtime.cpp','src/runtime/streams/AppStreamSessions.cpp','src/runtime/streams/ProviderQueueHost.cpp','src/runtime/drivers/ProviderGraphV2.cpp','src/runtime/drivers/ProviderModuleV2.cpp']
    includes=['','src','sdk/app','sdk/driver','sdk/hardware','lib/ArduinoJson/src','test/drivers/stubs','test']
    receipt={'runtime':PIN,'profile':new,'status':'running','scope':'focused host Runtime registration/cohort only','full_firmware_qualified':False,'physical_testing':False}
    for mode in ('normal','sanitized'):
        out=a.output/mode;out.mkdir()
        san=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer'] if mode=='sanitized' else []
        cmd=[os.environ.get('CXX','c++'),'-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-missing-field-initializers','-Wno-misleading-indentation','-g',*san,*['-I'+str(a.runtime/x) for x in includes],*selected,'-include',header,'-rdynamic','-no-pie','-pthread',*[a.runtime/x for x in sources],ROOT/'minimal/test/native_wifi_admission.cpp','-ldl','-o',out/'test']
        (out/'command.json').write_text(json.dumps(list(map(str,cmd)),indent=2)+'\n')
        run(cmd,out/'compile.log');run([out/'test',out/'stores'],out/'admission.log')
        receipt[mode]='passed'
    receipt['status']='passed'
    receipt['source_sha256']={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [header,ROOT/'profiles/native-wifi.cmake',ROOT/'minimal/test/native_wifi_admission.cpp']}
    (a.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('X4 successor source/profile and focused Runtime admission passed; full firmware remains unqualified')
if __name__=='__main__':main()
