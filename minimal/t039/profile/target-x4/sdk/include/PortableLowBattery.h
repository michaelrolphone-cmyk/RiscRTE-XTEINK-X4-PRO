#pragma once
/* Foreground app policy only: no hardware ABI or Runtime-owned Watch behavior.
 * Commit the edge before applying preferences. A reboot or partial failure must
 * never replay the edge and clobber later manual changes. Unknown battery
 * readings and charging alone neither enter nor rearm this policy. */
#include "PortableSleepPolicy.h"
#include "PortableRadioPolicy.h"
#include "PortablePowerStatus.h"
#define PORTABLE_LOW_BATTERY_KEY "battery_edge"
#define PORTABLE_LOW_BATTERY_THRESHOLD 10u
#define PORTABLE_LOW_BATTERY_IDLE_MS 20000u
#define PORTABLE_LOW_BATTERY_DEEP_MS 60000u
#define PORTABLE_LOW_BATTERY_BRIGHTNESS 15u
enum { PORTABLE_LOW_BATTERY_NONE=0, PORTABLE_LOW_BATTERY_ENTERED=1,
       PORTABLE_LOW_BATTERY_ERROR=2, PORTABLE_LOW_BATTERY_RETAINED=4 };
typedef struct { bool observed,low; } portable_low_battery;
static inline bool portable_low_battery_sample_valid(const risc_battery_sample_v1 *sample) {
    return sample&&sample->percent<=100&&!(sample->flags&RISC_BATTERY_PROFILE_MISSING)&&
        (!(sample->flags&PORTABLE_POWER_STATUS_VALID)||(sample->flags&PORTABLE_POWER_BATTERY_PRESENT));
}
static inline bool portable_low_battery_load(const risc_key_value_v1 *kv,bool *low) {
    *low=false;if(!pqa_preferences_valid(kv))return false;
    uint8_t bytes[4]={0};uint32_t size=0;
    int32_t rc=kv->get(kv->context,PORTABLE_LOW_BATTERY_KEY,bytes,sizeof(bytes),&size);
    if(rc==RISC_KEY_VALUE_NOT_FOUND)return true;
    if(rc!=RISC_KEY_VALUE_OK||size!=sizeof(bytes)||bytes[0]!=0x42||bytes[1]!=1||bytes[2]>1||
       bytes[3]!=(uint8_t)(bytes[2]^0xa5u))return false;
    *low=bytes[2]!=0;return true;
}
static inline bool portable_low_battery_save(const risc_key_value_v1 *kv,bool low) {
    if(!pqa_preferences_valid(kv))return false;
    const uint8_t bytes[]={0x42,1,low?1:0,(uint8_t)((low?1:0)^0xa5u)};
    int32_t rc=kv->put(kv->context,PORTABLE_LOW_BATTERY_KEY,bytes,sizeof(bytes));bool actual=false;
    return (rc==RISC_KEY_VALUE_OK||rc==RISC_KEY_VALUE_IO)&&portable_low_battery_load(kv,&actual)&&actual==low;
}
static inline unsigned portable_low_battery_observe(portable_low_battery *state,const risc_key_value_v1 *kv,
        const risc_battery_sample_v1 *sample) {
    if(!state||!portable_low_battery_sample_valid(sample))return PORTABLE_LOW_BATTERY_NONE;
    bool low=sample->percent<PORTABLE_LOW_BATTERY_THRESHOLD;
    if(state->observed&&state->low==low)return PORTABLE_LOW_BATTERY_NONE;
    /* Even an uncertain write is attempted once per observed crossing. */
    state->observed=true;state->low=low;
    bool stored=false;
    if(!portable_low_battery_load(kv,&stored))return PORTABLE_LOW_BATTERY_ERROR;
    if(stored==low)return PORTABLE_LOW_BATTERY_NONE;
    if(!portable_low_battery_save(kv,low))return PORTABLE_LOW_BATTERY_ERROR;
    if(!low)return PORTABLE_LOW_BATTERY_NONE;
    bool ok=true;
    if(!portable_sleep_timer_save(kv,false,PORTABLE_LOW_BATTERY_IDLE_MS))ok=false;
    if(!portable_sleep_timer_save(kv,true,PORTABLE_LOW_BATTERY_DEEP_MS))ok=false;
#ifdef PORTABLE_X4_IDLE_POLICY
    /* OFF is an intentional paper preference, including its saved way back.
     * Never turn it on during an unattended low-battery crossing. */
    unsigned brightness=PQA_BRIGHTNESS_DEFAULT;
    if(!pqa_preference_load(kv,PQA_BRIGHTNESS_KEY,PQA_BRIGHTNESS_DEFAULT,0,&brightness))ok=false;
    else if(brightness && !pqa_preference_save(kv,PQA_BRIGHTNESS_KEY,PORTABLE_LOW_BATTERY_BRIGHTNESS,0))ok=false;
#else
    if(!pqa_preference_save(kv,PQA_BRIGHTNESS_KEY,PORTABLE_LOW_BATTERY_BRIGHTNESS,10))ok=false;
#endif
    uint8_t flags=0;
    if(!portable_radio_load(kv,&flags)||!portable_radio_save(kv,(uint8_t)(flags&~3u)))ok=false;
    return PORTABLE_LOW_BATTERY_ENTERED|(ok?0:PORTABLE_LOW_BATTERY_ERROR);
}
static inline unsigned portable_low_battery_update(portable_low_battery *state,const risc_runtime_api_v1 *rt,
        const risc_battery_sample_v1 *sample) {
    if(!state||!portable_low_battery_sample_valid(sample))return PORTABLE_LOW_BATTERY_NONE;
    bool low=sample->percent<PORTABLE_LOW_BATTERY_THRESHOLD;
    if(state->observed&&state->low==low)return PORTABLE_LOW_BATTERY_NONE;
    risc_runtime_capability_v1 grant={.struct_size=sizeof(grant)};
    if(!rt||!rt->acquire||!rt->release||!rt->acquire(RISC_KEY_VALUE_CAPABILITY,1,1,&grant)) {
        state->observed=true;state->low=low;return PORTABLE_LOW_BATTERY_ERROR;
    }
    unsigned result=portable_low_battery_observe(state,grant.api,sample);
    if(!rt->release(&grant))result|=PORTABLE_LOW_BATTERY_RETAINED;
    return result;
}
