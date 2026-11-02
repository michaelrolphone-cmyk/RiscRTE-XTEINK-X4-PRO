#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <RiscHardwareConfigV1.h>
#include <RiscProviderSyncV1.h>
#include <RiscPlatformClockV1.h>
#include <RiscDisplayOutputPowerV1.h>
#include <RiscStorageVolumeV1.h>
#include <RiscFrontlightV1.h>
#include "../drivers/x4pro_power/X4PowerDeepV1.h"
#include "PortableHomePower.h"
#include "PortableDeskClock.h"
extern const risc_driver_v2 *x4_home_power_get(uint32_t);
extern const risc_driver_v2 *x4_home_display_get(uint32_t);
static const char *test;static bool terminal,panel_held,sd_prepared,sd_closed,alarm_ready,staged;
static unsigned calls,keys,entries;static uint64_t now=100;static uint16_t level=37;
typedef struct {bool locked,created;} lock_state;
static lock_state power_lock,display_lock;
static bool which(const char*s){return !strcmp(test,s);}
static void safe(void){assert(!terminal);calls++;}
static bool owner(void*c){(void)c;safe();return true;}
static bool create(void*c,uint64_t*out){safe();lock_state*s=c;assert(!s->created);s->created=true;*out=1;return true;}
static bool take(void*c,uint64_t token){safe();lock_state*s=c;assert(token==1&&s->created&&!s->locked);s->locked=true;return true;}
static bool unlock(void*c,uint64_t token){safe();lock_state*s=c;assert(token==1&&s->locked);s->locked=false;return true;}
static bool destroy(void*c,uint64_t token){safe();lock_state*s=c;assert(token==1&&s->created&&!s->locked);s->created=false;return true;}
static const risc_provider_sync_api_v1 psync={1,sizeof(psync),&power_lock,owner,create,take,unlock,destroy};
static const risc_provider_sync_api_v1 dsync={1,sizeof(dsync),&display_lock,owner,create,take,unlock,destroy};
static uint64_t ticks(void*c){(void)c;safe();return which("clock-backwards")&&keys>1?1:now;}
static void delay(void*c,uint32_t ms){(void)c;safe();assert(!panel_held&&!sd_closed&&ms==5);now+=ms;}
static const risc_platform_clock_api_v1 clock_api={1,sizeof(clock_api),NULL,ticks,delay};
static bool key(void*c,bool*out){(void)c;safe();keys++;if(which("key-retained")){terminal=true;return false;}*out=which("held-key");return true;}
static int32_t light(void*c,uint32_t ms,risc_light_sleep_result_v1*out){
 (void)c;safe();assert(!staged&&alarm_ready&&panel_held&&sd_closed&&level==0&&ms==1000);entries++;
 if(which("light-entry-retained")){terminal=true;return RISC_LIGHT_SLEEP_RETAINED;}
 if(which("light-entry-refused"))return RISC_LIGHT_SLEEP_BUSY;
 out->struct_size=sizeof(*out);return RISC_LIGHT_SLEEP_OK;
}
static int32_t deep(void*c,uint32_t ms){(void)c;safe();assert(staged&&alarm_ready&&panel_held&&sd_closed&&level==0&&ms==1000);entries++;
 if(which("native-retained")){terminal=true;return RISC_DEEP_SLEEP_RETAINED;}
 if(which("native-zero")){terminal=true;return 0;}
 if(which("native-unknown")){terminal=true;return -99;}
 return RISC_DEEP_SLEEP_BUSY;
}
static const x4_power_deep_v1 xpower={{1,sizeof(xpower),NULL,key,light},X4_POWER_DEEP_TAG,1,deep};
static bool seed(void*c,risc_display_frame_v1 f){(void)c;(void)f;return true;}
static int32_t panel_prepare(void*c,uint32_t budget){(void)c;safe();assert(alarm_ready&&(staged||!strncmp(test,"light-entry",11))&&budget==1500&&!panel_held&&!sd_closed);
 if(which("panel-retained")||which("panel-unknown")){terminal=true;return which("panel-retained")?RISC_DISPLAY_POWER_RETAINED:-99;}
 if(which("panel-refused"))return RISC_DISPLAY_POWER_BUSY;
 if(which("light-entry-expired"))now+=1001;
 panel_held=true;return 0;
}
static int32_t panel_resume(void*c,uint32_t budget){(void)c;safe();assert(!sd_closed&&budget==1500);
 if(which("panel-restore")){terminal=true;return RISC_DISPLAY_POWER_RETAINED;}panel_held=false;return 0;
}
static const risc_display_output_api_v1_power panel={.history={.base={.api_version=1,.struct_size=sizeof(panel)},.extension_tag=RISC_DISPLAY_HISTORY_TAG,.extension_version=1,.seed_previous=seed},.power_tag=RISC_DISPLAY_POWER_TAG,.power_version=1,.prepare=panel_prepare,.resume=panel_resume};
static bool storage_prepare(void*c){(void)c;safe();assert(panel_held&&alarm_ready);sd_prepared=true;return !which("storage-prepare");}
static bool storage_commit(void*c){(void)c;safe();assert(sd_prepared&&panel_held);sd_closed=true;return !which("storage-commit");}
static int32_t storage_resume(void*c){(void)c;safe();assert(panel_held&&sd_prepared);if(which("storage-retained")){terminal=true;return RISC_STORAGE_SLEEP_RETAINED;}sd_prepared=sd_closed=false;return which("media-unavailable")?RISC_STORAGE_SLEEP_MEDIA_UNAVAILABLE:RISC_STORAGE_SLEEP_READY;}
static bool legacy_commit(void*c){(void)c;assert(0);return false;}
static const risc_storage_volume_api_v1_sleep storage={.terminal={.power={.volume={.base={.api_version=1,.struct_size=sizeof(storage)}}},.extension_tag=RISC_STORAGE_POWER_COMMIT_TAG,.extension_version=1,.commit_power_down=legacy_commit},.sleep_tag=RISC_STORAGE_SLEEP_TAG,.sleep_version=1,.prepare_sleep=storage_prepare,.commit_sleep=storage_commit,.resume_sleep=storage_resume};
static bool get_light(void*c,uint16_t*out,uint16_t*max){(void)c;safe();if(which("light-read")){terminal=true;return false;}*out=level;*max=100;return true;}
static bool set_light(void*c,uint16_t value,uint16_t max){(void)c;safe();assert(max==100);if(which("light-off")||(which("light-restore")&&value)){terminal=true;return false;}level=value;return true;}
static const risc_frontlight_api_v1 frontlight={1,sizeof(frontlight),NULL,set_light,get_light};
static const risc_hardware_device_v1 power_hw={.api_version=1,.struct_size=sizeof(power_hw),.instance_id=17},panel_hw={.api_version=1,.struct_size=sizeof(panel_hw),.instance_id=3};
int main(int argc,char**argv){
 assert(argc==2);test=argv[1];const risc_driver_v2*p=x4_home_power_get(2),*d=x4_home_display_get(2);
 risc_provider_dependency_v1 pd[]={{"hardware.device",1,&power_hw},{"x4.power",1,&xpower},{"platform.sync",1,&psync},{"platform.clock",1,&clock_api},{RISC_DISPLAY_POWER_CAPABILITY,1,d->capability}};
 risc_provider_dependency_v1 dd[]={{"hardware.device",1,&panel_hw},{"display.output",1,&panel},{"storage.volume",1,&storage},{"display.frontlight",1,&frontlight},{"platform.sync",1,&dsync}};
 assert(!strcmp(p->capability_id,"power.sleep")&&!strcmp(d->capability_id,"display.power"));
 if(which("missing-binding")){assert(!p->start(pd,3)&&!d->start(dd,4));puts("missing typed binding refused PASS");return 0;}
 assert(d->start(dd,5)&&p->start(pd,5));
 portable_home_power s={.power=p->capability,.display=d->capability};
 if(which("enrolled-unavailable")){s.enrolled_wake_sources=true;assert(!portable_home_power_supported(&s));assert(p->quiesce()&&d->quiesce());return 0;}
 if(which("preprepare-pending")){bool pending=true;assert(s.power->sleep_wake_pending(s.power->context,&pending)&&!pending);assert(p->quiesce()&&d->quiesce());puts("Nonacknowledging cancellation before preparation PASS");return 0;}
 bool light_case=!strncmp(test,"light-entry",11);
 portable_desk_record record={.config={.time_format=1},.displayed_minute=1704067200,.has_image=true};strcpy(record.config.time_zone,"UTC");
 uint8_t bytes[PORTABLE_DESK_CLOCK_RECORD_BYTES];assert(portable_desk_encode(&record,bytes,sizeof(bytes)));staged=!light_case;
 int rc=portable_home_power_prepare(&s);
 if(rc==1){assert(!panel_held&&!sd_closed&&now>=130);alarm_ready=true;
  if(light_case){risc_light_sleep_result_v1 wake={.struct_size=sizeof(wake)};int result=s.power->light_sleep_for(s.power->context,1000,&wake);
   if(result==RISC_LIGHT_SLEEP_RETAINED)rc=portable_home_power_fence(&s);else{assert(result==RISC_LIGHT_SLEEP_OK||result==RISC_LIGHT_SLEEP_BUSY);rc=0;}}
  else rc=portable_home_power_hold(&s);
 }
 if(rc==1)rc=portable_home_power_enter(&s,1000);
 if(rc!=-2){int restored=portable_home_power_restore(&s);if(restored==-2)rc=-2;else assert(restored==1);}
 if(rc==-2){assert(s.retained);unsigned stopped=calls;assert(portable_home_power_restore(&s)==-2&&calls==stopped);}
 else{assert(!sd_prepared&&!sd_closed&&!panel_held&&level==37);assert(p->quiesce()&&d->quiesce());assert(!power_lock.created&&!display_lock.created);}
 assert((rc==-2)==terminal);
 portable_desk_record decoded;assert(portable_desk_decode(bytes,sizeof(bytes),&decoded)&&decoded.displayed_minute==record.displayed_minute);
 printf("X4 standard capability bridge %s: staged %u bytes, keys=%u entries=%u custody PASS\n",test,(unsigned)sizeof(bytes),keys,entries);return 0;
}
