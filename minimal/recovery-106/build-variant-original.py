#!/usr/bin/env python3
"""Reproduce the published Xtensa app recipe and record mounted-source hashes."""
from pathlib import Path
import sys,subprocess,hashlib,json,shutil
R=Path('/mnt/data/obd-side-by-side/work')
sys.path.insert(0,str(R/'Utilities/scripts'));from build_obd_dashboard import stage
sys.path.insert(0,str(R/'Drivers/scripts'));from normalize_xtensa_relocations import normalize
CC=str(R/'toolchain/bin/xtensa-esp32s3-elf-gcc')
FLAGS=['-std=c11','-Os','-fPIC','-mtext-section-literals','-mlongcalls','-ffreestanding','-fno-builtin','-fvisibility=hidden','-ffunction-sections','-fdata-sections','-fstack-usage','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(src,out,test=False):
 out.mkdir(parents=True,exist_ok=True)
 inc=stage(R/'Runtime',R/'System',R/'Drivers',out)
 obj=[];commands=[]
 def run(c):commands.append(c);subprocess.run(c,check=True)
 flags=FLAGS+(['-DOBD_SIDE_BY_SIDE_TEST=1'] if test else [])
 for n in ('elm','dashboard','math','app'):
  o=out/(n+'.o');obj.append(o);run([CC,*flags,'-I'+str(inc),'-c',str(src/'Apps/obd_dashboard'/f'{n}.c'),'-o',str(o)])
 mapping=out/'exports.map';mapping.write_text('{ global: app_main; risc_resident_app_descriptor_v1; local: *; };\n')
 elf=out/('obd_test.elf' if test else 'obd_dashboard.elf')
 run([CC,*flags,'-nostdlib','-nostartfiles','-shared','-Wl,--no-relax','-Wl,--hash-style=sysv','-Wl,--gc-sections','-Wl,--version-script='+str(mapping),*map(str,obj),'-lgcc','-o',str(elf)])
 normalize(elf)
 symbols=subprocess.check_output([CC.removesuffix('gcc')+'nm','-D',str(elf)],text=True)
 imports={l.split()[-1] for l in symbols.splitlines() if ' U ' in ' '+l}
 exports={l.split()[-1] for l in symbols.splitlines() if len(l.split())>=3 and l.split()[-2] in ('T','D','B','R')}
 assert imports<= {'risc_runtime_get_api','memcpy','memset','memcmp','strlen','strcmp','strncmp','strstr','strcspn','snprintf'},imports
 assert exports=={'app_main','risc_resident_app_descriptor_v1'},exports
 stack={}
 for p in out.glob('*.su'):
  for l in p.read_text().splitlines():f,n,k=l.split('\t');stack[f]=int(n)
 assert max(stack.values())<=1536
 manifest=src/('Apps/obd_test.json' if test else 'Apps/obd_dashboard.json');shutil.copyfile(manifest,out/'manifest.json')
 result={'version':json.loads(manifest.read_text())['version'],'bytes':elf.stat().st_size,'sha256':sha(elf),'imports':sorted(imports),'exports':sorted(exports),'stack_frames':stack,'source_files':{str(p.relative_to(src)):sha(p) for p in (src/'Apps/obd_dashboard').glob('*') if p.is_file()},'sdk_files':{p.name:sha(p) for p in inc.glob('*.h')},'commands':commands,'runtime_source':'a91edf3fada6a559ec107186dd163d0c8da10d29','system_source':'a3504d4f8f342d9d78383978e8b70032d0097c23','app_source_base':'a9c6dfea6800676bc272c118cab80c6c41e45c9a','hardware_tested':False}
 (out/'build.json').write_text(json.dumps(result,indent=2)+'\n');print(elf,elf.stat().st_size,sha(elf))
 return elf


if __name__=='__main__':
 a=build(R/'Utilities',R/'target-default');assert a.read_bytes()==(R/'target-baseline/obd_dashboard.elf').read_bytes()
 a=build(R/'Utilities',R/'target-test',True);b=build(R/'Utilities',R/'target-test-repeat',True);assert a.read_bytes()==b.read_bytes()
 print('Unmodified default ELF and deterministic test ELF PASS')
