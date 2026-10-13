#include "runtime/drivers/NativeProviderPolicyValidationV1.h"
#include "runtime/packages/ElfAdmission.h"
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>
#include "private/elf_types.h"
#include "RiscBankStoreV1.h"
extern "C" bool esp_elf_validate_file(const uint8_t*,size_t);
namespace CohortElf {
static uint32_t ticks=0;
static bool safe=true;static const char* missing=nullptr;
static bool operationSafe(){return safe;}
static uint32_t millis(){return ticks;}
static void vTaskDelay(unsigned n){ticks+=n;}
static uintptr_t elf_find_sym_default(const char* name){
 if(missing && !strcmp(missing,name))return 0;
 static const char* exports[]={"__divdf3","__errno","__fixunsdfsi","__floatunsidf","__getreent","__gtdf2","__ltdf2","_ctype_","calloc","clock_gettime","free","getopt_long","isalpha","longjmp","malloc","memchr","memcmp","memcpy","memmove","memset","optarg","opterr","optind","optopt","qsort","realloc","risc_runtime_get_api","setjmp","snprintf","strcasecmp","strcat","strchr","strcmp","strcpy","strcspn","strerror","strftime","strlen","strncasecmp","strncat","strncmp","strncpy","strnlen","strrchr","strstr","strtod","strtof","strtol","strtoul","tolower","vsnprintf"};
 for(const char* symbol:exports)if(!strcmp(name,symbol))return 1;return 0;
}
bool allowedImport(const char*name){return RiscPackages::ordinaryImport(name);}
enum class ElfRole {Application,Driver,Either};
bool admitElf(const uint8_t*bytes,size_t n,ElfRole role=ElfRole::Application,
              const RuntimeProviders::NativeProviderPolicyV1*policy=nullptr){
 if(!operationSafe()||n>RISC_BANK_APP_MAX)return false;
 if(role!=ElfRole::Driver)policy=nullptr;
 if(policy&&!RuntimeProviders::nativeProviderImageValid(*policy,bytes,n))return false;
 return RiscPackages::admitElf(bytes,n,role,policy!=nullptr,{esp_elf_validate_file,
   [](const char*name){return allowedImport(name)&&elf_find_sym_default(name);},
   operationSafe,[](){vTaskDelay(1);},[]()->uint32_t{return millis();}});
}
static bool file(void* context,const char* path,bool provider){
 std::ifstream input(path,std::ios::binary);if(!input)return false;
 std::vector<uint8_t> bytes(std::istreambuf_iterator<char>(input),{});
 if(!admitElf(bytes.data(),bytes.size(),provider?ElfRole::Driver:ElfRole::Application))return false;
 ++*static_cast<unsigned*>(context);return true;
}
}
