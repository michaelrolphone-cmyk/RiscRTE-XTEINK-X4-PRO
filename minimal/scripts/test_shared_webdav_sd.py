#!/usr/bin/env python3
"""Production async-v3 X4 SD/FatFs + shared WebDAV. Host only; no device access."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser()
for n in ('system','sdk','shared-storage','reader','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[2];out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
a.system=a.system.resolve();a.sdk=a.sdk.resolve();a.shared_storage=a.shared_storage.resolve();a.reader=a.reader.resolve()
fixture=root/'minimal/test/sd_async_test.c'
s=fixture.read_text().replace('int main(void){','int original_async_fixture_main(void){')
s+='''
const risc_storage_volume_api_v1* webdav_real_volume(void){
 format(false);assert(t5_driver_get(2));assert(START());assert(async_begin(NULL,&session)==0);request(RISC_STORAGE_ASYNC_REFRESH,NULL);assert(finish()==0);end_session();
 return (const risc_storage_volume_api_v1*)&asynchronous_api;
}
static risc_storage_export_token_t dav_export;
void webdav_real_export(int exported){uint64_t blocks=0;uint32_t bytes=0;if(exported)assert(export_begin(NULL,&dav_export,&blocks,&bytes)==RISC_STORAGE_EXPORT_READY);else assert(export_end(NULL,dav_export)==RISC_STORAGE_EXPORT_READY);}
void webdav_real_absent(int missing){absent=missing;assert(refresh(NULL));}
void webdav_real_worker(int active){if(active)assert(async_begin(NULL,&session)==0);else end_session();}
void webdav_real_finish(void){assert(!has_handles());verify_cleanup();}
'''
(out/'bridge.c').write_text(s)
# Route the unchanged fake wire model to the same canonical CRC declarations.
proto=a.reader/'Drivers/x4pro_board/x4pro_proto.h'
(out/'x4pro_proto.h').write_text(proto.read_text().replace('#include "../storage_fatfs/sd_protocol.h"','#include <sd_protocol.h>'))
sanitize=['-fsanitize=undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
incs=['-I'+str(x) for x in (out,a.sdk,a.shared_storage,a.reader/'Drivers/x4pro_board',a.reader,root/'minimal/test')]
commands=[]
def run(cmd):commands.append(cmd);subprocess.run(cmd,check=True)
run(['cc','-std=c11','-O1','-g','-Wno-overflow','-DX4PRO_SD_ALLOW_LEGACY_GPIO=1',*sanitize,*incs,'-c',str(out/'bridge.c'),'-o',str(out/'bridge.o')])
for name,src in [('ff',a.shared_storage/'fatfs/ff.c'),('unicode',a.shared_storage/'fatfs/ffunicode.c'),('sha2',a.system/'lib/RemoteFiles/vendor/tinydtls_sha2/sha2.c')]:
 run(['cc','-std=c11','-O1','-g',*sanitize,*incs,'-c',str(src),'-o',str(out/(name+'.o'))])
run(['c++','-std=c++17','-O1','-g',*sanitize,'-I'+str(a.system/'lib/RemoteFiles'),'-I'+str(a.system/'lib/PortableApps/include'),*[str(a.system/'lib/RemoteFiles'/(n+'.cpp')) for n in ('WebDavCore','WebDavVolume','WebDavProperties','WebDavSession')],str(root/'minimal/test/webdav_sd_integration.cpp'),*[str(out/(n+'.o')) for n in ('bridge','ff','unicode','sha2')],'-o',str(out/'test')])
result=subprocess.run([str(out/'test')],check=True,text=True,capture_output=True);print(result.stdout)
inputs={}
for base in (root/'minimal/test',root/'minimal/drivers/x4pro_sd',a.shared_storage,a.sdk,a.system/'lib/RemoteFiles',a.system/'lib/PortableApps/include'):
 for f in base.rglob('*'):
  if f.is_file() and f.suffix in ('.c','.cpp','.h','.inc'):inputs[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
inputs[str(proto)]=hashlib.sha256(proto.read_bytes()).hexdigest()
(out/'evidence.json').write_text(json.dumps(dict(scope='Production SD/FatFs and WebDAV; modeled native worker/sector and TCP boundary; UBSan; no hardware',result=result.stdout,commands=commands,source_sha256=inputs),indent=2)+'\n')
