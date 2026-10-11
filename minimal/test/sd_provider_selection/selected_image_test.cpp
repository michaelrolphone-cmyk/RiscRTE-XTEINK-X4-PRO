// Exercise the unmodified Runtime/Graph/ModuleV2 image-selection path with real
// delivered Xtensa bytes. Only final machine-code execution is substituted by
// a host provider after exact-byte equality and the production ELF validator.
#include "bootstrap/Runtime.h"
#include <RiscStorageVolumeV1.h>
#include <esp_elf.h>
#include <private/esp_dlcache.h>
#include <dlfcn.h>
#include <cassert>
#include <fstream>
#include <vector>
#include <string>
#include <cstring>
#include <cstdio>
extern "C" bool esp_elf_validate_file(const uint8_t*,size_t);
static std::string root,sd,selected,mode;
static std::vector<unsigned char> expected;
static FILE* media;
static unsigned opens,closes,readers,fallbacks,defaults,starts,stops;
static bool present=true,missing=false,corrupt=false;
static std::vector<unsigned char> bytes(const std::string&p){std::ifstream f(p,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};}
static void write(const char*n,const std::string&s){std::ofstream f(root+"/"+n);f<<s;assert(f);}
extern "C" void proof_event(unsigned e){if(e==0)++defaults;else if(e==1)++starts;else ++stops;}
extern "C" const risc_storage_volume_api_v1* proof_volume(){
 static risc_storage_volume_api_v1 v{};v.api_version=1;v.struct_size=sizeof(v);
 v.refresh=[](void*){return present;};v.ready=[](void*){return present;};
 v.file_open_read=[](void*,const char*p,uint64_t*n)->uint32_t{assert(std::string(p)=="/"+selected);if(missing)return 0;assert(!media);media=fopen((sd+p).c_str(),"rb");if(!media)return 0;assert(!fseek(media,0,SEEK_END));*n=ftell(media);rewind(media);++opens;return 1;};
 v.file_read=[](void*,uint32_t h,void*out,size_t n)->size_t{assert(h==1&&media&&n<=4096);bool first=ftell(media)==0;size_t got=fread(out,1,n>333?333:n,media);if(first&&corrupt&&got)static_cast<unsigned char*>(out)[0]=0;return got;};
 v.file_close=[](void*,uint32_t h,bool){assert(h==1&&media);bool ok=!fclose(media);media=nullptr;++closes;return ok;};return &v;
}
extern "C" void* __real_dlopen(const char*,int);
static void check(const uint8_t*p,size_t n){assert(!media&&opens==closes);assert(n==expected.size()&&!memcmp(p,expected.data(),n));assert(esp_elf_validate_file(p,n));}
extern "C" void* __wrap_dlopen(const char* path,int flags){
 if(path){auto b=bytes(path);if(b.size()>20&&b[18]==94&&b[19]==0){check(b.data(),b.size());++fallbacks;return __real_dlopen((root+"/plugin-host.elf").c_str(),flags);}}
 return __real_dlopen(path,flags);
}
extern "C" void* esp_elf_malloc(uint32_t n,bool){return malloc(n);}
extern "C" void esp_elf_free(void*p){free(p);}
extern "C" void* esp_dlopen_reader_instance(const char*name,esp_dl_image_reader reader,void*c){
 assert(!media);elf_file_t f{};assert(!reader(c,name,&f));check(f.payload,f.size);++readers;esp_elf_free(f.payload);return __real_dlopen((root+"/plugin-host.elf").c_str(),RTLD_NOW|RTLD_LOCAL);
}
int main(int argc,char**argv){
 assert(argc==7);root=argv[1];sd=argv[2];selected=argv[3];mode=argv[4];expected=bytes(argv[5]);const auto current=bytes(argv[6]);
 present=mode!="absent";missing=mode=="missing";corrupt=mode=="corrupt";
 assert(esp_elf_validate_file(expected.data(),expected.size()));assert(esp_elf_validate_file(current.data(),current.size()));
 {std::ofstream f(root+"/plugin.elf",std::ios::binary);f.write((const char*)current.data(),current.size());assert(f);}
 write("board.json",R"({"schema":"riscrte.board-hardware","schema_version":1,"board_id":"test","revision":"unspecified","buses":[],"devices":[{"instance_id":9,"chip":{"vendor":"test","model":"gpio","revision":"unspecified"},"compatible":"test,gpio","config_type":"gpio.bank","config_version":1,"config":{"pins":[5],"active_high":true,"pull_up":false,"debounce_us":0,"long_press_us":0,"click_min_us":0}}]})");
 write("sd.json",R"({"type":"driver","id":"sd-test","version":"1.0.0","driver_abi":2,"architecture":"xtensa-esp32s3","file_name":"sd.elf","requires":[{"capability":"hardware.device","api":1}],"provides":[{"capability":"storage.volume","api":1}],"hardware_compatibility":[{"compatible":"test,gpio","revisions":["unspecified"],"config_type":"gpio.bank","config_version":1}]})");
 write("plugin.json",R"({"type":"driver","id":"sd-plugin","version":"1.0.0","driver_abi":2,"architecture":"xtensa-esp32s3","file_name":"plugin.elf","requires":[],"provides":[{"capability":"test.plugin","api":1}]})");
 const std::string boot=R"({"board":"board.json","default_app":"default.elf","provider_activation":"eager","drivers":[{"manifest":"sd.json","instance_id":9},{"manifest":"plugin.json","image_source":{"volume_instance":9,"path":")"+selected+R"(","internal_fallback":true}}],"app_capabilities":[]})";
 write("boot.json",boot);
 RiscBoot::Port port{[](){return true;},[](risc_runtime_health_v1*){return true;},[](uint32_t){},[](const char*){return true;}};
 {RiscBoot::Runtime r(port);if(!r.prepare(root.c_str())){fprintf(stderr,"prepare: %s\n",r.error());return 1;}if(!r.run()){fprintf(stderr,"run: %s\n",r.error());return 1;}assert(!r.retained());}
 assert(defaults==1&&starts==stops&&!media&&opens==closes);
 const bool fallback=!present||missing||corrupt;assert(readers==(fallback?0u:1u)&&fallbacks==(fallback?1u:0u));
 printf("Runtime selected-byte proof mode=%s bytes=%zu path=%s source=%s opens=%u closes=%u PASS\n",mode.c_str(),expected.size(),selected.c_str(),fallback?"internal":"SD",opens,closes);
}
