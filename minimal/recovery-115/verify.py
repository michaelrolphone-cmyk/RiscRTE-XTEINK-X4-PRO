#!/usr/bin/env python3
"""Admit the full .115 store against pinned Runtime and native BIN exports.
Recovered .105 fixtures are source evidence; native export addresses are re-read
from the unchanged firmware BIN, not assumed from the fixture's name list.
"""
from pathlib import Path
import argparse,os,sys,json,hashlib,subprocess,shutil,io,concurrent.futures
p=argparse.ArgumentParser(description=__doc__)
for n in ('runtime','x4','output','fixtures','native-proof','baseline-store'):
 p.add_argument('--'+n,required=True,type=Path)
p.add_argument('--mode',choices=['normal','undefined','asan'],default='normal')
a=p.parse_args()
for key,value in vars(a).items():
 if isinstance(value,Path): setattr(a,key,value.resolve())
rt=a.runtime;out=a.output
sys.path[:0]=[str(a.x4/'minimal/scripts'),str(rt/'scripts')]
from native_binary_exports import exports
from spiffs_image import read_image
from elftools.elf.elffile import ELFFile
report=json.loads((out/'assembly-report.json').read_text())
raw=(out/'X4-0.1.115-T057-OBD-Test-factory-erases-data-0x0.bin').read_bytes()
assert len(raw)==0x1000000 and hashlib.sha256(raw).hexdigest()==report['image_sha256']
current=read_image(raw[0x2f0000:0x800000],0x510000)
meta=json.loads(current['cohort.json']);native=raw[0x10000:0x10000+meta['firmware_size']]
oldproof=json.loads(a.native_proof.read_text())
lookup,proof=exports(native,{t['table']:[row['name'] for row in t['rows']] for t in oldproof['tables']})
assert lookup==oldproof['exports']
(out/'evidence').mkdir(exist_ok=True)
(out/'evidence/native-resolver.json').write_text(json.dumps(proof,indent=2)+'\n')
original={p.relative_to(a.baseline_store).as_posix():p.read_bytes() for p in a.baseline_store.rglob('*') if p.is_file()}
assert set(current)==set(original)
assert sorted(n for n in current if current[n]!=original[n])==['boot.json','cohort.json','obd_test.json','ui-scene/driver.elf','ui-scene/manifest.json']
mode=a.mode;d=out/'evidence'/('admission-'+mode);d.mkdir(parents=True,exist_ok=True)
for name in ['strict.cpp','fixture.cpp','cohort_elf_admission.h']:
 shutil.copyfile(a.fixtures/name,d/name)
(d/'app_data_admission_backend.h').write_text('''#pragma once
#include "bootstrap/AppDataBackend.h"
// Presence/authority only; these counted boundaries must never be invoked.
static RiscBoot::AppDataBackend admissionAppData(unsigned* calls) {
  return {calls,
    [](void* c,uint32_t,const char*,uint32_t*,uint64_t*)->int32_t {
      ++*static_cast<unsigned*>(c);return RISC_APP_DATA_UNAVAILABLE;
    },
    [](void* c,uint32_t,const char*,uint64_t,void*,uint32_t,uint32_t*,uint64_t*)->int32_t {
      ++*static_cast<unsigned*>(c);return RISC_APP_DATA_UNAVAILABLE;
    },
    [](void* c,uint32_t,const char*,uint64_t,const void*,uint32_t)->int32_t {
      ++*static_cast<unsigned*>(c);return RISC_APP_DATA_UNAVAILABLE;
    },
    [](void*) {return true;}
  };
}
''')
incs=[rt/n for n in ('src','sdk/app','sdk/driver','sdk/hardware','lib/ArduinoJson/src','test/drivers/stubs','lib/elf_loader/include','test/native_bank_stubs')]+[d,rt]
flags=['-std=c++17','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-Wno-misleading-indentation','-DRISC_APP_POLICY_ROWS=24','-DRISC_APP_REQUIREMENT_ROWS=24','-DRISC_INSTALLED_APP_CAPACITY=64','-DRISC_PROVIDER_CAPACITY=40',*['-I'+str(i) for i in incs]]
san=(['-fsanitize='+('address,undefined' if mode=='asan' else 'undefined'),'-fno-sanitize-recover=all','-fno-omit-frame-pointer'] + ([] if sys.platform=='darwin' else ['-no-pie'])) if mode!='normal' else []
flags+=san
# Clang diagnoses an existing Runtime promotion counter unused in this host
# configuration; keep the pinned production source untouched.
if sys.platform=='darwin': flags+=['-Wno-unused-but-set-variable']
def run(c,**kw):return subprocess.run(list(map(str,c)),check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1'),**kw)
run(['cc','-std=c11',*san,*['-I'+str(i) for i in incs],'-c',rt/'lib/elf_loader/src/esp_elf_validate.c','-o',d/'validate.o'])
run(['c++',*flags,d/'strict.cpp',d/'validate.o','-o',d/'strict'])
import zipfile
with zipfile.ZipFile(out/report['sd_file']) as z:
 for name in ('Apps/obd-dashboard/obd_dashboard.elf','Apps/obd-test/obd_test.elf'):
  data=z.read(name);elf=ELFFile(io.BytesIO(data));imports=sorted({sym.name for sec in elf.iter_sections() if sec['sh_type'] in ('SHT_DYNSYM','SHT_SYMTAB') for sym in sec.iter_symbols() if sym.name and sym['st_shndx']=='SHN_UNDEF'})
  assert set(imports)<=set(lookup)
  target=d/Path(name).name;target.write_bytes(data);run([d/'strict','app',target,*imports],stdout=subprocess.DEVNULL)
rows=[]
for n,b in sorted(current.items()):
 if not n.endswith('.elf'):continue
 elf=ELFFile(io.BytesIO(b));imports=sorted({s.name for sec in elf.iter_sections() if sec['sh_type'] in ('SHT_DYNSYM','SHT_SYMTAB') for s in sec.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'})
 assert set(imports)<=set(lookup),(n,set(imports)-set(lookup))
 role='driver' if n.endswith('/driver.elf') else 'app'
 run([d/'strict',role,out/'store'/n,*imports],stdout=subprocess.DEVNULL)
 rows.append({'file':n,'sha256':hashlib.sha256(b).hexdigest(),'imports':imports})
(d/'elf-results.json').write_text(json.dumps(rows,indent=2)+'\n');print(mode,'strict role/import/unsafe/missing-import cases PASS',len(rows),flush=True)
defs=['STORE_ADMISSION_APP_DATA','RISC_PAIRED_APP_DATA=1','STORE_ADMISSION_COHORT','STORE_ADMISSION_KV_V2','STORE_ADMISSION_RUNTIME_FEATURES','STORE_ADMISSION_RADIO_IQ','STORE_ADMISSION_IQ_LIFECYCLE','STORE_ADMISSION_RADIO','STORE_ADMISSION_HCI','STORE_ADMISSION_I2S_RX','STORE_ADMISSION_UPDATE_PLATFORMS','STORE_ADMISSION_COLD_BOOT','STORE_ADMISSION_CROWN_PROFILE','STORE_ADMISSION_FILE_SOURCE','STORE_ADMISSION_USB_PHY','STORE_ADMISSION_DIAGNOSTIC_SOURCE','RISC_RUNTIME_ATOMIC_KEY_VALUE=1']
flags+=['-D'+v for v in defs]
sources=[rt/n for n in ['src/bootstrap/Json.cpp','src/bootstrap/Board.cpp','src/bootstrap/Runtime.cpp','src/runtime/drivers/ProviderGraphV2.cpp','src/runtime/drivers/ProviderModuleV2.cpp','src/ports/esp32s3/CpuPort.cpp','src/runtime/streams/AppStreamSessions.cpp','src/runtime/streams/ProviderQueueHost.cpp']]+[d/'fixture.cpp']
def compile_one(p):
 obj=d/(p.stem+'.o');run(['c++',*flags,'-c',p,'-o',obj],stdout=subprocess.DEVNULL);return obj
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:objects=list(pool.map(compile_one,sources))
run(['c++',*flags,*objects,d/'validate.o',* ([] if sys.platform=='darwin' else ['-rdynamic','-ldl']),'-o',d/'cohort'])
p=run([d/'cohort',a.baseline_store,out/'store'],capture_output=True,text=True)
(d/'cohort.stdout').write_text(p.stdout);(d/'cohort.stderr').write_text(p.stderr);result=json.loads(p.stdout)
assert result['prepared'] and result['cohort_validated'] and result['hardware_calls']==result['storage_calls']==0,result
(d/'cohort-report.json').write_text(json.dumps(result,indent=2)+'\n');print(mode,'production Runtime/CpuPort complete store admission PASS',result,flush=True)
