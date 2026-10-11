#!/usr/bin/env python3
"""Exercise production installed-app registration with the composed OBD store.

Reuses a completed strict-admission host fixture. Only an active invocation and
inert platform callbacks are supplied by the harness; Runtime's native catalog
policy parsing, reservation matching and transaction code are unmodified.
Does not execute the target ELF, SD hardware, display or Bluetooth radio.
"""
import argparse,json,os,subprocess
from pathlib import Path


def run(runtime,tools,admission,store,output,sanitize=False):
    output.mkdir(parents=True,exist_ok=False)
    original=(admission/'runtime_store_admission.cpp').read_text()
    mark='  const bool prepared = runtime.prepare(argv[1]);'
    assert original.count(mark)==1
    original=original.replace('#include <cstdio>', '#include <cstdio>\n#include "'+str(runtime/'src/bootstrap/Runtime.cpp')+'"',1)
    original=original.replace(mark,mark+r'''
  assert(prepared);
  // A caller-owned active invocation is the input boundary of the native
  // installed-app API. No hand-built boot reservations or rewritten manifests.
  currentRuntime=&runtime;
  runtime.mainInvocation_.active_=true;
  const auto* api=&runtime.installation_[0].api;
  std::ifstream manifest(std::string(argv[1])+"/obd_dashboard.json");
  std::string text(std::istreambuf_iterator<char>(manifest),{});
  assert(!text.empty());
  risc_install_candidate_v1 item{"Apps/obd-dashboard/manifest.json",text.c_str()};
  risc_install_result_v1 result{};const uint32_t slot=128;
  size_t before=runtime.appCount();
  assert(api->namespaced(api->context,&item,&slot,1,&result,false,true)==RISC_INSTALL_OK);
  assert(result.status==RISC_INSTALL_OK && runtime.appCount()==before);
  assert(api->namespaced(api->context,&item,&slot,1,&result,false,false)==RISC_INSTALL_OK);
  assert(result.status==RISC_INSTALL_OK && runtime.appCount()==before+1);
  size_t bound=runtime.policyCount_;
  for(size_t i=runtime.bootPolicyCount_;i<runtime.policyCount_;++i)
    if(!strcmp(runtime.policies_[i].id,"obd-dashboard"))bound=i;
  assert(bound<runtime.policyCount_);
  const auto& policy=runtime.policies_[bound];
  assert(policy.enabled && !policy.catalogAuthority && policy.count==3);
  assert(runtime.residentForeground_[bound] && !runtime.residentLegacy_[bound]);
  assert(!strcmp(policy.sourcePath,"/Apps/obd-dashboard/obd_dashboard.elf"));
  assert(!strcmp(policy.grants[0].capability,"ui.scene"));
  assert(!strcmp(policy.grants[1].capability,"bluetooth.serial"));
  assert(policy.grants[1].driver>=0 &&
    !strcmp(runtime.drivers_[policy.grants[1].driver].id,"ble-serial"));
  assert(!strcmp(policy.grants[2].capability,"storage.volume") && policy.grants[2].instance==9);
  assert(policy.grants[2].driver>=0 && runtime.drivers_[policy.grants[2].driver].instance==9);
  assert(api->namespaced(api->context,&item,&slot,1,&result,false,false)==RISC_INSTALL_OK &&
    result.status==RISC_INSTALL_OK && runtime.appCount()==before+1);
  char path[193];
  assert(api->admit(api->context,"Apps/not-obd/manifest.json",text.c_str(),path,sizeof(path))==RISC_INSTALL_DENIED);
  std::string changed=text;size_t at=changed.find("bluetooth.serial");assert(at!=std::string::npos);
  changed.replace(at,strlen("bluetooth.serial"),"bluetooth.hci");
  assert(api->admit(api->context,item.manifest_path,changed.c_str(),path,sizeof(path))==RISC_INSTALL_DENIED);
  assert(runtime.appCount()==before+1);
  assert(!hardwareCalls && !storageCalls);
  runtime.mainInvocation_.active_=false;currentRuntime=nullptr;
  puts("OBD catalog: exact SD manifest, native reservation, transaction dry-run/commit, foreground lifecycle, selected BLE plus SD-instance-9 grants, idempotent discovery, denied path/grant changes PASS");
  return 0;
''')
    target=output/'catalog.cpp';target.write_text(original)
    inc=[runtime/n for n in ('src','sdk/app','sdk/driver','sdk/hardware','lib/ArduinoJson/src','test/drivers/stubs','lib/elf_loader/include','test/native_bank_stubs')]+[admission,tools/'tests']
    flags=['-std=c++17','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-Wno-misleading-indentation','-rdynamic']
    if sanitize:flags+=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie']
    defines=['RISC_APP_REQUIREMENT_ROWS=24','RISC_APP_POLICY_ROWS=24','RISC_INSTALLED_APP_CAPACITY=64','RISC_PROVIDER_CAPACITY=40',
      'STORE_ADMISSION_APP_DATA','RISC_PAIRED_APP_DATA=1','STORE_ADMISSION_COHORT','STORE_ADMISSION_KV_V2','STORE_ADMISSION_RUNTIME_FEATURES','STORE_ADMISSION_RADIO_IQ','STORE_ADMISSION_IQ_LIFECYCLE','STORE_ADMISSION_RADIO','STORE_ADMISSION_HCI','STORE_ADMISSION_I2S_RX','STORE_ADMISSION_UPDATE_PLATFORMS']
    sources=[runtime/n for n in ('src/bootstrap/Json.cpp','src/bootstrap/Board.cpp','src/runtime/drivers/ProviderGraphV2.cpp','src/runtime/drivers/ProviderModuleV2.cpp','src/ports/esp32s3/CpuPort.cpp','src/runtime/streams/AppStreamSessions.cpp','src/runtime/streams/ProviderQueueHost.cpp')]
    cmd=['c++',*flags,*['-I'+str(p) for p in inc],*['-D'+s for s in defines],*map(str,sources),str(target),str(admission/'validate.o'),'-ldl','-o',str(output/'catalog')]
    subprocess.run(cmd,check=True)
    result=subprocess.run([str(output/'catalog'),str(store),str(store)],check=True,text=True,capture_output=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'))
    (output/'result.log').write_text(result.stdout+result.stderr);print(result.stdout)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('runtime','tools','admission','store','output'):p.add_argument('--'+key,type=lambda v:Path(v).resolve(),required=True)
    p.add_argument('--sanitize',action='store_true');a=p.parse_args();run(**vars(a))
