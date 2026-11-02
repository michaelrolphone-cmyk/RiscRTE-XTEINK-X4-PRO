/* Provider-owned standard capability bridge. Underlying x4.power owns GPIO3
 * and board keepalive; no physical identity escapes power.sleep. */
#include "../x4pro_power/X4PowerDeepV1.h"
#include <RiscPowerSleepV1.h>
#include <RiscProviderV2.h>
#include <RiscHardwareConfigV1.h>
#include <RiscProviderSyncV1.h>
#include <RiscPlatformClockV1.h>
#include <string.h>
static const x4_power_deep_v1 *power;
static const risc_provider_sync_api_v1 *sync_api;
static const risc_platform_clock_api_v1 *clock_api;
static uint64_t mutex;
static bool started,prepared,retained;
static bool enter(void){return !retained&&started&&sync_api&&sync_api->is_owner(sync_api->context)&&sync_api->try_lock(sync_api->context,mutex);}
static bool leave(void){if(!sync_api->unlock(sync_api->context,mutex)){retained=true;return false;}return true;}
static bool prepare(void *unused){
 (void)unused;if(!enter())return false;
 bool ok=false,down=true;uint64_t began=clock_api->monotonic_ms(clock_api->context),neutral=began,previous=began;
 if(began!=UINT64_MAX)for(unsigned n=0;n<80;n++){
  if(!power->power.read_key(power->power.context,&down)){retained=true;return false;}
  uint64_t now=clock_api->monotonic_ms(clock_api->context);
  if(now==UINT64_MAX||now<previous||now-previous>400u||now-began>400u)break;
  previous=now;if(down)neutral=now;else if(now-neutral>=30u){ok=true;break;}
  clock_api->sleep_ms(clock_api->context,5);
 }
 prepared=ok;return leave()&&ok;
}
static bool resume(void *unused){(void)unused;if(!enter())return false;prepared=false;return leave();}
static bool pending(void *unused,bool *out){
 (void)unused;if(!out||!enter())return false;bool down=true;
 if(!prepared||!power->power.read_key(power->power.context,&down)){retained=true;return false;}
 if(!leave())return false;
 *out=down;return true;
}
static int32_t timed(void *unused,uint32_t duration){
 (void)unused;if(retained)return RISC_DEEP_SLEEP_RETAINED;
 if(!duration||duration>RISC_TIMED_SLEEP_MAX_MS)return RISC_DEEP_SLEEP_INVALID;
 if(!enter())return RISC_DEEP_SLEEP_CONTEXT;
 int32_t rc=prepared?power->deep_sleep_for(power->power.context,duration):RISC_DEEP_SLEEP_BUSY;
 if(rc>=0||rc==RISC_DEEP_SLEEP_RETAINED||rc<RISC_DEEP_SLEEP_UNSUPPORTED){retained=true;return RISC_DEEP_SLEEP_RETAINED;}
 return leave()?rc:RISC_DEEP_SLEEP_RETAINED;
}
static int32_t light_for(void *unused,uint32_t duration,risc_light_sleep_result_v1 *out){
 (void)unused;if(retained)return RISC_LIGHT_SLEEP_RETAINED;if(!enter())return RISC_LIGHT_SLEEP_CONTEXT;
 int32_t rc=prepared?power->power.light_sleep(power->power.context,duration,out):RISC_LIGHT_SLEEP_BUSY;
 if(rc==RISC_LIGHT_SLEEP_RETAINED||rc<RISC_LIGHT_SLEEP_UNSUPPORTED||rc>0){retained=true;return RISC_LIGHT_SLEEP_RETAINED;}
 return leave()?rc:RISC_LIGHT_SLEEP_RETAINED;
}
static int32_t light(void*c,risc_light_sleep_result_v1*out){return light_for(c,0,out);}
static int32_t untimed(void*c){(void)c;return RISC_DEEP_SLEEP_UNSUPPORTED;}
static bool start(const risc_provider_dependency_v1 *deps,size_t count){
 if(started||mutex||retained||!deps||count!=4)return false;
 const risc_hardware_device_v1 *hw=NULL;
 const x4_power_deep_v1 *p=NULL;const risc_provider_sync_api_v1*s=NULL;const risc_platform_clock_api_v1*t=NULL;
 for(size_t i=0;i<count;i++){if(!deps[i].api||deps[i].api_version!=1||!deps[i].capability_id)return false;
  if(!strcmp(deps[i].capability_id,"hardware.device")&&!hw)hw=deps[i].api;
  else if(!strcmp(deps[i].capability_id,X4_POWER_CAPABILITY)&&!p)p=x4_power_deep(deps[i].api);
  else if(!strcmp(deps[i].capability_id,"platform.sync")&&!s)s=deps[i].api;
  else if(!strcmp(deps[i].capability_id,"platform.clock")&&!t)t=deps[i].api;else return false;
 }
 if(!hw||hw->api_version!=1||hw->struct_size<sizeof(*hw)||hw->instance_id!=17||!p||!p->power.read_key||!p->power.light_sleep||!s||s->api_version!=1||s->struct_size<sizeof(*s)||!s->create||!s->destroy||!s->try_lock||!s->unlock||!s->is_owner||!s->is_owner(s->context)||!t||t->api_version!=1||t->struct_size<sizeof(*t)||!t->monotonic_ms||!t->sleep_ms)return false;
 power=p;sync_api=s;clock_api=t;
 if(!s->create(s->context,&mutex)||!mutex){retained=true;return false;}started=true;return true;
}
static bool quiesce(void){
 if(retained||prepared)return false;
 if(!mutex)return true;
 if(!enter())return false;
 started=false;
 if(!leave()||!sync_api->destroy(sync_api->context,mutex)){retained=true;return false;}
 mutex=0;power=NULL;sync_api=NULL;clock_api=NULL;return true;
}
static void stop(void){}
static const risc_power_sleep_api_v1 api={.api_version=1,.struct_size=RISC_POWER_TIMED_DEEP_SLEEP_SIZE,.prepare_sleep=prepare,.resume=resume,.light_sleep=light,.deep_sleep=untimed,.light_sleep_for=light_for,.sleep_wake_pending=pending,.deep_sleep_for=timed};
static const risc_driver_v2 driver={2,sizeof(driver),"x4pro-home-power",RISC_POWER_SLEEP_CAPABILITY,1,&api,start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t abi){return abi==2?&driver:NULL;}
