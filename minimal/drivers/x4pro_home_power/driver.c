#ifdef X4_HOME_BRIDGE_SINGLETON
#include "../x4pro_power/X4PowerCoordinationV1.h"
#endif
/* Provider-owned standard capability bridge. Underlying x4.power owns GPIO3
 * and board keepalive; no physical identity escapes power.sleep. */
#include "../x4pro_power/X4PowerDeepV1.h"
#include <RiscPowerSleepV1.h>
#include <RiscDisplayPowerV1.h>
#include <RiscProviderV2.h>
#include <RiscHardwareConfigV1.h>
#include <RiscProviderSyncV1.h>
#include <RiscPlatformClockV1.h>
#include <string.h>
static const x4_power_deep_v1 *power;
static const risc_display_power_api_v1 *display_power;
static bool light_display_touched;
#ifdef X4_HOME_BRIDGE_SINGLETON
typedef x4_power_coordination_api_v1 home_coordination_api;
#else
typedef risc_provider_sync_api_v1 home_coordination_api;
#endif
static const home_coordination_api *sync_api;
static const risc_platform_clock_api_v1 *clock_api;
static uint64_t mutex;
static bool started,prepared,retained;
#ifdef X4_HOME_BRIDGE_SINGLETON
static bool coordination_result(int32_t rc){
 if(rc==X4_COORDINATION_OK)return true;
 if(rc!=X4_COORDINATION_BUSY)retained=true;
 return false;
}
static bool enter(void){
 if(retained||!started||!sync_api)return false;
 if(!coordination_result(sync_api->owner(sync_api->context)))return false;
 return coordination_result(sync_api->try_lock(sync_api->context,mutex));
}
static bool leave(void){if(sync_api->unlock(sync_api->context,mutex)!=X4_COORDINATION_OK){retained=true;return false;}return true;}
#else
static bool enter(void){return !retained&&started&&sync_api&&sync_api->is_owner(sync_api->context)&&sync_api->try_lock(sync_api->context,mutex);}
static bool leave(void){if(!sync_api->unlock(sync_api->context,mutex)){retained=true;return false;}return true;}
#endif

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
static bool resume(void *unused){
 (void)unused;if(!enter())return false;
 if(light_display_touched){
  if(display_power->resume_status(display_power->context)!=0){retained=true;return false;}
  light_display_touched=false;
 }
 prepared=false;return leave();
}
static bool pending(void *unused,bool *out){
 (void)unused;if(!out||!enter())return false;bool down=true;
 if(!power->power.read_key(power->power.context,&down)){retained=true;return false;}
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
/* App reconciles the unchanged alarm ticket before invoking this callback.
 * Provider closes the selected panel/SD after that boundary and charges its
 * processing time to the supplied duration. Checked resume restores it first. */
static int32_t light_for(void *unused,uint32_t duration,risc_light_sleep_result_v1 *out){
 (void)unused;if(retained)return RISC_LIGHT_SLEEP_RETAINED;
 if(duration>RISC_TIMED_SLEEP_MAX_MS)return RISC_LIGHT_SLEEP_INVALID;
 if(!enter())return RISC_LIGHT_SLEEP_CONTEXT;
 int32_t rc=RISC_LIGHT_SLEEP_BUSY;
 if(prepared&&!light_display_touched){
  uint64_t before=clock_api->monotonic_ms(clock_api->context);
  if(before==UINT64_MAX)return leave()?RISC_LIGHT_SLEEP_BUSY:RISC_LIGHT_SLEEP_RETAINED;
  light_display_touched=true;
  int32_t hold=display_power->prepare_deep_sleep(display_power->context);
  if(hold==RISC_DEEP_SLEEP_RETAINED||hold>0||hold<RISC_DEEP_SLEEP_UNSUPPORTED){retained=true;return RISC_LIGHT_SLEEP_RETAINED;}
  if(hold==0){
   uint64_t now=clock_api->monotonic_ms(clock_api->context);
   if(now!=UINT64_MAX&&now>=before&&(!duration||now-before<duration)){
    uint32_t left=duration?duration-(uint32_t)(now-before):0;
    rc=power->power.light_sleep(power->power.context,left,out);
   }
  }
 }
 if(rc==RISC_LIGHT_SLEEP_RETAINED||rc<RISC_LIGHT_SLEEP_UNSUPPORTED||rc>0){retained=true;return RISC_LIGHT_SLEEP_RETAINED;}
 return leave()?rc:RISC_LIGHT_SLEEP_RETAINED;
}
static int32_t light(void*c,risc_light_sleep_result_v1*out){return light_for(c,0,out);}
static int32_t untimed(void*c){(void)c;return RISC_DEEP_SLEEP_UNSUPPORTED;}
static bool start(const risc_provider_dependency_v1 *deps,size_t count){
#ifdef X4_HOME_BRIDGE_SINGLETON
 if(started||mutex||retained||!deps||count!=3)return false;
#else
 if(started||mutex||retained||!deps||count!=5)return false;
 const risc_hardware_device_v1 *hw=NULL;
#endif
 const risc_display_power_api_v1*d=NULL;
 const x4_power_deep_v1 *p=NULL;const home_coordination_api*s=NULL;const risc_platform_clock_api_v1*t=NULL;
 for(size_t i=0;i<count;i++){if(!deps[i].api||deps[i].api_version!=1||!deps[i].capability_id)return false;
#ifndef X4_HOME_BRIDGE_SINGLETON
  if(!strcmp(deps[i].capability_id,"hardware.device")&&!hw)hw=deps[i].api;
  else
#endif
  if(!strcmp(deps[i].capability_id,X4_POWER_CAPABILITY)&&!p)p=x4_power_deep(deps[i].api);
  else if(!strcmp(deps[i].capability_id,RISC_DISPLAY_POWER_CAPABILITY)&&!d)d=deps[i].api;
#ifndef X4_HOME_BRIDGE_SINGLETON
  else if(!strcmp(deps[i].capability_id,"platform.sync")&&!s)s=deps[i].api;
#endif
  else if(!strcmp(deps[i].capability_id,"platform.clock")&&!t)t=deps[i].api;else return false;
 }
#ifdef X4_HOME_BRIDGE_SINGLETON
 s=x4_power_coordination(p?&p->power:NULL);
#endif
#ifndef X4_HOME_BRIDGE_SINGLETON
 if(!hw||hw->api_version!=1||hw->struct_size<sizeof(*hw)||hw->instance_id!=17)return false;
#endif
 if(!d||d->api_version!=1||d->struct_size<RISC_DISPLAY_POWER_RESUME_STATUS_SIZE||!d->prepare_deep_sleep||!d->resume_status||!p||!p->power.read_key||!p->power.light_sleep||!s||s->api_version!=1||s->struct_size<sizeof(*s)||!s->create||!s->destroy||!s->try_lock||!s->unlock
#ifndef X4_HOME_BRIDGE_SINGLETON
 ||!s->is_owner||!s->is_owner(s->context)
#endif
||!t||t->api_version!=1||t->struct_size<sizeof(*t)||!t->monotonic_ms||!t->sleep_ms)return false;
#ifdef X4_HOME_BRIDGE_SINGLETON
 if(!coordination_result(s->owner(s->context)))return false;
#endif
 power=p;display_power=d;sync_api=s;clock_api=t;
#ifdef X4_HOME_BRIDGE_SINGLETON
 int32_t created=s->create(s->context,&mutex);
 if(created!=X4_COORDINATION_OK){if(created!=X4_COORDINATION_BUSY||mutex)retained=true;return false;}
 if(!mutex){retained=true;return false;}
#else
 if(!s->create(s->context,&mutex)||!mutex){retained=true;return false;}
#endif
 started=true;return true;
}
static bool quiesce(void){
 if(retained||prepared||light_display_touched)return false;
 if(!mutex)return true;
 if(!enter())return false;
 started=false;
 if(!leave())return false;
#ifdef X4_HOME_BRIDGE_SINGLETON
 if(sync_api->destroy(sync_api->context,mutex)!=X4_COORDINATION_OK){retained=true;return false;}
#else
 if(!sync_api->destroy(sync_api->context,mutex)){retained=true;return false;}
#endif
 mutex=0;power=NULL;display_power=NULL;sync_api=NULL;clock_api=NULL;return true;
}
static void stop(void){}
static const risc_power_sleep_api_v1 api={.api_version=1,.struct_size=RISC_POWER_TIMED_DEEP_SLEEP_SIZE,.prepare_sleep=prepare,.resume=resume,.light_sleep=light,.deep_sleep=untimed,.light_sleep_for=light_for,.sleep_wake_pending=pending,.deep_sleep_for=timed};
#ifdef X4_HOME_BRIDGE_SINGLETON
#define X4_HOME_BRIDGE_ID "x4pro-home-power-singleton"
#else
#define X4_HOME_BRIDGE_ID "x4pro-home-power"
#endif
static const risc_driver_v2 driver={2,sizeof(driver),X4_HOME_BRIDGE_ID,RISC_POWER_SLEEP_CAPABILITY,1,&api,start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t abi){return abi==2?&driver:NULL;}
