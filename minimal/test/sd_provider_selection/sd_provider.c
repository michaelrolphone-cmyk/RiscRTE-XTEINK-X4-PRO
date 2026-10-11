#include <RiscProviderV2.h>
#include <RiscStorageVolumeV1.h>
extern const risc_storage_volume_api_v1* proof_volume(void);
extern void proof_event(unsigned);
static bool start(const risc_provider_dependency_v1*d,size_t n){(void)d;proof_event(1);return n==1;}
static bool quiesce(void){proof_event(2);return true;}
static void stop(void){}
static risc_driver_v2 api={2,sizeof(api),"sd-test","storage.volume",1,0,start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2*t5_driver_get(uint32_t v){api.capability=proof_volume();return v==2?&api:0;}
