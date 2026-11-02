#ifdef X4_HOME_BRIDGE_SINGLETON
#include "../x4pro_power/X4PowerCoordinationV1.h"
#endif
/* Provider-owned physical closure for the selected retained X4 display.
 * TIMER needs panel/frontlight/storage, not touch, navigation, RTC or radios.
 * App owns record staging, foreground consumer drains and alarm reconciliation. */
#include <RiscDisplayPowerV1.h>
#include <RiscDisplayOutputPowerV1.h>
#include <RiscStorageVolumeV1.h>
#include <RiscFrontlightV1.h>
#include <RiscProviderSyncV1.h>
#include <RiscProviderV2.h>
#include <RiscHardwareConfigV1.h>
#include <string.h>
static const risc_display_output_api_v1 *output;
static const risc_display_output_api_v1_power *panel;
static const risc_storage_volume_api_v1_sleep *storage;
static const risc_frontlight_api_v1 *frontlight;
static const risc_provider_sync_api_v1 *sync_api;
static uint64_t mutex;
static bool started,retained,dark,panel_touched,storage_touched;
static uint16_t saved_level,saved_maximum;
static bool enter(void){return !retained&&started&&sync_api&&sync_api->is_owner(sync_api->context)&&sync_api->try_lock(sync_api->context,mutex);}
static bool leave(void){if(!sync_api->unlock(sync_api->context,mutex)){retained=true;return false;}return true;}
static int32_t fence(void){retained=true;return RISC_DEEP_SLEEP_RETAINED;}
static bool prepare(void *unused){
 (void)unused;if(!enter())return false;if(dark||panel_touched||storage_touched){(void)fence();return false;}
 if(!frontlight->get_level(frontlight->context,&saved_level,&saved_maximum)||!saved_maximum||saved_level>saved_maximum){(void)fence();return false;}
 dark=true;
 if(!frontlight->set_level(frontlight->context,0,saved_maximum)){(void)fence();return false;}
 return leave();
}
static int32_t hold(void *unused){
 (void)unused;if(retained)return RISC_DEEP_SLEEP_RETAINED;if(!enter())return RISC_DEEP_SLEEP_CONTEXT;
 int32_t rc=RISC_DEEP_SLEEP_BUSY;
 if(dark&&!panel_touched&&!storage_touched){
  panel_touched=true;int32_t status=panel->prepare(output->context,RISC_DISPLAY_POWER_MAX_BUDGET_MS);
  if(status==RISC_DISPLAY_POWER_RETAINED||status>0||status<RISC_DISPLAY_POWER_PLATFORM)return fence();
  if(status==RISC_DISPLAY_POWER_OK){
   storage_touched=true;
   if(storage->prepare_sleep(storage->terminal.power.volume.base.context)&&storage->commit_sleep(storage->terminal.power.volume.base.context))rc=0;
  }
 }
 return leave()?rc:RISC_DEEP_SLEEP_RETAINED;
}
static int32_t resume_status(void *unused){
 (void)unused;if(retained)return RISC_DEEP_SLEEP_RETAINED;if(!enter())return RISC_DEEP_SLEEP_CONTEXT;
 if(storage_touched){
  int32_t rc=storage->resume_sleep(storage->terminal.power.volume.base.context);
  if(rc!=RISC_STORAGE_SLEEP_READY&&rc!=RISC_STORAGE_SLEEP_MEDIA_UNAVAILABLE)return fence();
  storage_touched=false;
 }
 if(panel_touched){if(panel->resume(output->context,RISC_DISPLAY_POWER_MAX_BUDGET_MS)!=RISC_DISPLAY_POWER_OK)return fence();panel_touched=false;}
 if(dark){if(!frontlight->set_level(frontlight->context,saved_level,saved_maximum))return fence();dark=false;}
 return leave()?0:RISC_DEEP_SLEEP_RETAINED;
}
static bool resume(void*c){return resume_status(c)==0;}
static bool start(const risc_provider_dependency_v1 *deps,size_t count){
#ifdef X4_HOME_BRIDGE_SINGLETON
 if(started||mutex||retained||!deps||count!=4)return false;
#else
 if(started||mutex||retained||!deps||count!=5)return false;
 const risc_hardware_device_v1 *hw=NULL;
#endif
#ifdef X4_HOME_BRIDGE_SINGLETON
 const x4_power_v1 *coordination_power=NULL;
#endif
 const risc_display_output_api_v1*d=NULL;const risc_storage_volume_api_v1_sleep*v=NULL;const risc_frontlight_api_v1*f=NULL;const risc_provider_sync_api_v1*s=NULL;
 for(size_t i=0;i<count;i++){if(!deps[i].api||deps[i].api_version!=1||!deps[i].capability_id)return false;
#ifndef X4_HOME_BRIDGE_SINGLETON
  if(!strcmp(deps[i].capability_id,"hardware.device")&&!hw)hw=deps[i].api;
  else
#endif
  if(!strcmp(deps[i].capability_id,"display.output")&&!d)d=deps[i].api;
#ifdef X4_HOME_BRIDGE_SINGLETON
  else if(!strcmp(deps[i].capability_id,X4_POWER_CAPABILITY)&&!coordination_power)coordination_power=deps[i].api;
#endif
  else if(!strcmp(deps[i].capability_id,"storage.volume")&&!v)v=risc_storage_volume_sleep(deps[i].api);
  else if(!strcmp(deps[i].capability_id,"display.frontlight")&&!f)f=deps[i].api;
#ifndef X4_HOME_BRIDGE_SINGLETON
  else if(!strcmp(deps[i].capability_id,"platform.sync")&&!s)s=deps[i].api;
#endif
  else return false;
 }
#ifdef X4_HOME_BRIDGE_SINGLETON
 s=x4_power_coordination(coordination_power);
#endif
 const risc_display_output_api_v1_power*p=risc_display_output_power(d);
#ifndef X4_HOME_BRIDGE_SINGLETON
 if(!hw||hw->api_version!=1||hw->struct_size<sizeof(*hw)||hw->instance_id!=3)return false;
#endif
 if(!p||!v||!f||f->api_version!=1||f->struct_size<sizeof(*f)||!f->get_level||!f->set_level||!s||s->api_version!=1||s->struct_size<sizeof(*s)||!s->create||!s->destroy||!s->try_lock||!s->unlock||!s->is_owner||!s->is_owner(s->context))return false;
 output=d;panel=p;storage=v;frontlight=f;sync_api=s;
 if(!s->create(s->context,&mutex)||!mutex){retained=true;return false;}started=true;return true;
}
static bool quiesce(void){
 if(retained||dark||panel_touched||storage_touched)return false;
 if(!mutex)return true;
 if(!enter())return false;
 started=false;
 if(!leave()||!sync_api->destroy(sync_api->context,mutex)){retained=true;return false;}
 mutex=0;output=NULL;panel=NULL;storage=NULL;frontlight=NULL;sync_api=NULL;return true;
}
static void stop(void){}
static const risc_display_power_api_v1 api={1,sizeof(api),NULL,prepare,resume,hold,resume_status};
#ifdef X4_HOME_BRIDGE_SINGLETON
#define X4_HOME_BRIDGE_ID "x4pro-home-display-power-singleton"
#else
#define X4_HOME_BRIDGE_ID "x4pro-home-display-power"
#endif
static const risc_driver_v2 driver={2,sizeof(driver),X4_HOME_BRIDGE_ID,RISC_DISPLAY_POWER_CAPABILITY,1,&api,start,stop,quiesce};
__attribute__((visibility("default"))) const risc_driver_v2 *t5_driver_get(uint32_t abi){return abi==2?&driver:NULL;}
