// Focused host proof against the unmodified Runtime 0.2.24 implementation.
// Adapted from test/removable_runtime_test.cpp and test/resident_shell_test.cpp.
// The host dlopen bridge substitutes x86 host fixtures for Xtensa mappings.
#include "bootstrap/Runtime.h"
#include <RiscResidentShellV1.h>
#include <esp_elf.h>
#include <private/esp_dlcache.h>
#include <dlfcn.h>
#include <unistd.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
using namespace RiscBoot;
namespace {
std::string root,id,mode,imagePath,manifestText;
Runtime* runtime=nullptr;
const risc_runtime_api_v1* api=nullptr;
const risc_installation_v1* installer=nullptr;
unsigned maps[2]{},unmaps[2]{},entries[2]{},inits[2]{},finis[2]{};
unsigned providerStarts=0,providerStops=0,opens=0,closes=0,live=0,dispatches=0,failures=0;
unsigned observedChildRole=99;
uint64_t hostToken=0,childToken=0;
std::vector<uint8_t> payload;
size_t offset=0;
bool installed=false,expectedForeground=false,expectedReject=false;
void save(const std::string& name,const JsonDocument& doc){std::string bytes;serializeJson(doc,bytes);std::ofstream(root+"/"+name)<<bytes;}
JsonDocument manifest(const std::string& name){
 JsonDocument doc;doc["type"]="application";doc["id"]=name;doc["version"]="1.0.0";
 doc["architecture"]="xtensa-esp32s3";doc["file_name"]=name+".elf";doc["entry"]="app_main";doc["requires"].to<JsonArray>();return doc;
}
void setup(){
 std::ofstream(root+"/board.json")<<R"({"schema":"riscrte.board-hardware","schema_version":1,"board_id":"test","revision":"unspecified","buses":[],"devices":[{"instance_id":9,"chip":{"vendor":"test","model":"gpio","revision":"unspecified"},"compatible":"test,gpio","config_type":"gpio.bank","config_version":1,"config":{"pins":[5],"active_high":true,"pull_up":false,"debounce_us":0,"long_press_us":0,"click_min_us":0}}]})";
 std::ofstream(root+"/sd.json")<<R"({"type":"driver","id":"sd-test","version":"1.0.0","driver_abi":2,"architecture":"xtensa-esp32s3","file_name":"sd.elf","requires":[{"capability":"hardware.device","api":1},{"capability":"platform.installation","api":1}],"provides":[{"capability":"storage.volume","api":1}],"hardware_compatibility":[{"compatible":"test,gpio","revisions":["unspecified"],"config_type":"gpio.bank","config_version":1}]})";
 JsonDocument boot;boot["board"]="board.json";boot["default_app"]="host.elf";boot["provider_activation"]="eager";
 auto driver=boot["drivers"].to<JsonArray>().add<JsonObject>();driver["manifest"]="sd.json";driver["instance_id"]=9;
 boot["installation"]["volume_instance"]=9;boot["installation"]["grants"].to<JsonArray>();
 auto policies=boot["app_capabilities"].to<JsonArray>();
 auto host=manifest("host");save("host.json",host);
 auto hp=policies.add<JsonObject>();hp["manifest"]="host.json";hp["grants"].to<JsonArray>();
 // A nonloaded foreground reservation keeps the legacy-only control policy valid.
 auto anchor=manifest("anchor");save("anchor.json",anchor);
 auto ap=policies.add<JsonObject>();ap["manifest"]="anchor.json";ap["grants"].to<JsonArray>();
 auto shell=boot["resident_shell"].to<JsonObject>();shell["api"]=1;shell["host"]="host.elf";
 auto foreground=shell["foreground"].to<JsonArray>();foreground.add("anchor.elf");
 auto legacy=shell["legacy"].to<JsonArray>();
 const bool actualLegacy=id=="gameboy" || id=="model_viewer" || id=="hollow_trail";
 if(actualLegacy)legacy.add(id+".elf");else foreground.add(id+".elf");
 auto app=manifest(id);save(id+".json",app);
 auto authority=policies.add<JsonObject>();authority["manifest"]=id+".json";authority["catalog_authority"]=true;
 authority["image_source"]["volume_instance"]=9;authority["image_source"]["path"]=imagePath;authority["grants"].to<JsonArray>();
 if(mode=="foreground" || expectedReject)app["runtime_lifecycle"]="foreground";
 if(mode=="legacy")app["runtime_lifecycle"]="legacy";
 serializeJson(app,manifestText);save("installed-manifest.json",app);save("boot.json",boot);
}
int32_t dispatch(void*,const risc_resident_request_v1* request,risc_resident_reply_v1* reply){
 assert(request->reason==RISC_RESIDENT_CHECKPOINT_POLL);assert(maps[0]==unmaps[0]+1);
 risc_resident_client_v1 host{};host.struct_size=sizeof(host);assert(api->resident_shell(&host));
 assert(host.role==RISC_RESIDENT_ROLE_HOST && host.invocation==hostToken);++dispatches;reply->flags=0;return RISC_RESIDENT_OK;
}
void failed(void*,const risc_resident_failure_v1* failure){assert(expectedReject);assert(failure->kind==RISC_RESIDENT_FAILURE_ABI && failure->status==RISC_RESIDENT_INCOMPATIBLE);++failures;}
void breadcrumb(const char* app,uint64_t token,uint32_t phase,uint32_t role){
 if(phase!=RISC_FAILURE_PHASE_MAIN)return;
 if(app==imagePath){observedChildRole=role;childToken=token;}
}
FailureEvidenceBackend evidence{nullptr,nullptr,breadcrumb,[](int32_t,const char*){assert(false);}};
}
extern "C" void removable_installation(const void* p){installer=static_cast<const risc_installation_v1*>(p);}
extern "C" void removable_bound_settings(const void*){assert(false);}
extern "C" unsigned removable_event(unsigned event,unsigned){if(event==2)++providerStarts;else if(event==3){assert(!live);++providerStops;}else assert(false);return 0;}
extern "C" const risc_storage_volume_api_v1* removable_volume(){
 static risc_storage_volume_api_v1 volume{};volume.api_version=1;volume.struct_size=sizeof(volume);
 volume.ready=[](void*){return true;};volume.refresh=[](void*){return true;};
 volume.file_open_read=[](void*,const char* path,uint64_t* size)->uint32_t{assert(path=="/"+imagePath && !live);live=1;++opens;offset=0;*size=payload.size();return 1;};
 volume.file_read=[](void*,uint32_t handle,void* out,size_t size)->size_t{assert(handle==1 && live && size<=4096);size=std::min(size_t(333),std::min(size,payload.size()-offset));memcpy(out,payload.data()+offset,size);offset+=size;return size;};
 volume.file_close=[](void*,uint32_t handle,bool){assert(handle==1 && live);live=0;++closes;return true;};
 return &volume;
}
extern "C" void* esp_elf_malloc(uint32_t size,bool){return malloc(size);}
extern "C" void esp_elf_free(void* ptr){free(ptr);}
extern "C" bool esp_elf_validate_file(const uint8_t* ptr,size_t size){return size>52 && !memcmp(ptr,"\177ELF",4);}
extern "C" void* esp_dlopen_reader_instance(const char* name,esp_dl_image_reader reader,void* context){
 assert(!live);elf_file_t file{};assert(reader(context,name,&file)==0 && !live);
 char path[]="/tmp/riscrte-installed-role-XXXXXX";int fd=mkstemp(path);assert(fd>=0);
 FILE* out=fdopen(fd,"wb");assert(out);assert(fwrite(file.payload,1,file.size,out)==file.size);assert(!fclose(out));
 esp_elf_free(file.payload);void* module=dlopen(path,RTLD_NOW|RTLD_LOCAL);if(!module)fprintf(stderr,"dlopen: %s\n",dlerror());unlink(path);assert(module);return module;
}
extern "C" void test_resident_map(unsigned role){assert(role<2);++maps[role];}
extern "C" void test_resident_unmap(unsigned role){assert(role<2);++unmaps[role];}
extern "C" int test_resident_init(unsigned role){assert(role<2);++inits[role];return 0;}
extern "C" void test_resident_fini(unsigned role){assert(role<2);++finis[role];}
extern "C" void test_resident_main(unsigned role,unsigned* visits){
 assert(role<2 && ++*visits==1);++entries[role];api=risc_runtime_get_api(1);assert(api);
 risc_resident_client_v1 client{};client.struct_size=sizeof(client);
 if(role==0){
  assert(api->resident_shell(&client) && client.role==RISC_RESIDENT_ROLE_HOST);hostToken=client.invocation;
  risc_resident_callbacks_v1 callbacks{1,sizeof(callbacks),nullptr,dispatch,failed,nullptr};assert(client.register_shell(client.invocation,&callbacks)==RISC_RESIDENT_OK);
  if(installed){assert(entries[0]==2 && entries[1]==1 && maps[1]==unmaps[1]);return;}
  assert(installer && runtime->appCount()==3);installed=true;
  char launch[193]{};const std::string path="Apps/"+id+"/manifest.json";
  assert(installer->admit(installer->context,path.c_str(),manifestText.c_str(),launch,sizeof(launch))==RISC_INSTALL_OK);
  assert(launch==imagePath && runtime->appCount()==4);
  // The disabled catalog-authority alias remains separate from its SD admission.
  risc_resident_result_v1 result{};result.struct_size=sizeof(result);
  const auto status=client.run_foreground(client.invocation,launch,&result);
  if(expectedReject){assert(status==RISC_RESIDENT_INCOMPATIBLE && result.status==status);assert(entries[1]==0 && inits[1]==0 && failures==1);}
  else if(expectedForeground){assert(status==RISC_RESIDENT_OK && result.status==status);assert(entries[1]==1 && dispatches==1 && maps[0]==1 && !unmaps[0]);}
  else {assert(status==RISC_RESIDENT_HANDOFF && result.status==status);assert(entries[1]==0);}
  return;
 }
 assert(!expectedReject && live==0 && opens==closes);
 if(expectedForeground){
  assert(maps[0]==1 && unmaps[0]==0 && inits[0]==1 && finis[0]==0);
  assert(api->resident_shell(&client) && client.role==RISC_RESIDENT_ROLE_FOREGROUND);
  assert(observedChildRole==2 && childToken==client.invocation && client.invocation!=hostToken);
  risc_resident_request_v1 request{sizeof(request),RISC_RESIDENT_CHECKPOINT_POLL,0,0};risc_resident_reply_v1 reply{sizeof(reply),0};
  assert(client.checkpoint(client.invocation,&request,&reply)==RISC_RESIDENT_OK);
 }else{
  assert(maps[0]==1 && unmaps[0]==1 && inits[0]==1 && finis[0]==1);
  assert(!api->resident_shell(&client) && observedChildRole==0);
 }
}
int main(int argc,char** argv){
 assert(argc==5);root=argv[1];id=argv[2];mode=argv[3];const std::string fixture=argv[4];
 imagePath="Apps/"+id+"/"+id+".elf";expectedReject=mode=="bad-descriptor" || mode=="missing-descriptor";expectedForeground=mode=="foreground";
 std::ifstream input(root+"/"+fixture,std::ios::binary);assert(input);payload.assign(std::istreambuf_iterator<char>(input),{});assert(payload.size()>52);
 setup();Port port{[](){return true;},[](risc_runtime_health_v1*){return true;},[](uint32_t){},[](const char*){return true;}};port.failureEvidence=&evidence;
 Runtime instance(port);runtime=&instance;if(!runtime->prepare(root.c_str())){fprintf(stderr,"prepare: %s\n",runtime->error());abort();}
 assert(runtime->run() && !runtime->retained());assert(opens==1 && closes==1 && !live && providerStarts==providerStops);
 assert(maps[0]==unmaps[0] && maps[1]==unmaps[1] && maps[1]==1);
 assert(entries[0]==(expectedForeground || expectedReject?1u:2u));assert(entries[1]==(expectedReject?0u:1u));
 assert(inits[0]==finis[0] && inits[1]==finis[1]);
 printf("PASS app=%s mode=%s child_role=%s host_entries=%u host_unloads=%u child_entries=%u checkpoints=%u descriptor_rejections=%u sd_opens=%u sd_closes=%u\n",id.c_str(),mode.c_str(),expectedReject?"rejected":observedChildRole==2?"2":"0",entries[0],unmaps[0],entries[1],dispatches,failures,opens,closes);
}
