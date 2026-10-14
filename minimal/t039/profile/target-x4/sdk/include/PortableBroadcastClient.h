#pragma once
#include "TelemetryBroadcastV1.h"
#include "PortableRadioPolicy.h"
#include <string.h>
#ifndef PORTABLE_BROADCAST_CUSTODY_SAFE
#define PORTABLE_BROADCAST_CUSTODY_SAFE() true
#endif
typedef struct {
    risc_runtime_capability_v1 grant,storage;
    const telemetry_broadcast_v1 *api;
    const risc_runtime_api_v1 *runtime;
    telemetry_broadcast_policy_v1 policy;
    uint32_t loaded_at;
    bool loaded,save_failed;
} portable_broadcast_client;
static inline bool portable_broadcast_open(portable_broadcast_client *c,const risc_runtime_api_v1 *rt) {
    memset(c,0,sizeof(*c));c->runtime=rt;c->grant.struct_size=sizeof(c->grant);
    if(!rt->acquire(TELEMETRY_BROADCAST_CAPABILITY,1,0,&c->grant))return false;
    const telemetry_broadcast_v1 *p=c->grant.api;
    if(!p||p->api_version!=1||p->struct_size<sizeof(*p)||!p->step||!p->pause||!p->status||!p->enumerate||!p->read)return false;
    c->api=p;c->policy.struct_size=sizeof(c->policy);return true;
}
static inline bool portable_broadcast_control_load(const risc_key_value_v1 *kv,bool *enabled) {
    *enabled=false;if(!pqa_preferences_valid(kv))return false;
    uint8_t b[4];uint32_t n=0;int32_t rc=kv->get(kv->context,TELEMETRY_BROADCAST_KEY,b,sizeof(b),&n);
    if(rc==RISC_KEY_VALUE_NOT_FOUND){
#ifdef PORTABLE_BLE_BROADCAST_DEFAULT_OFF
        *enabled=false;
#else
        *enabled=true;
#endif
        return true;
    }
    if(rc!=RISC_KEY_VALUE_OK||n!=4||b[0]!=0x62||b[1]!=1||b[2]>1||b[3]!=(uint8_t)(b[2]^0xa5u))return false;
    *enabled=b[2]!=0;return true;
}
static inline bool portable_broadcast_release_storage(portable_broadcast_client *c) {
    if(!PORTABLE_BROADCAST_CUSTODY_SAFE())return false;
    if(c->storage.api&&!c->runtime->release(&c->storage))return false;
    memset(&c->storage,0,sizeof(c->storage));return true;
}
static inline bool portable_broadcast_pause(portable_broadcast_client *c) {
    c->loaded=false;return PORTABLE_BROADCAST_CUSTODY_SAFE() && (!c->api || c->api->pause(c->api->context));
}
static inline bool portable_broadcast_step(portable_broadcast_client *c,bool allow) {
    if(!PORTABLE_BROADCAST_CUSTODY_SAFE()||!c->api)return false;
    if(c->storage.api){
        /* Retained app storage admits only cleanup before normal service I/O. */
        if(!portable_broadcast_pause(c)||!portable_broadcast_release_storage(c))return false;
    }
    risc_runtime_health_v1 health={.struct_size=sizeof(health)};
    if(!c->runtime->health(&health))return portable_broadcast_pause(c);
    if(!c->save_failed && (!c->loaded||(uint32_t)(health.uptime_ms-c->loaded_at)>=1000u)) {
#ifdef PORTABLE_BROADCAST_PAUSE_POLICY_READS
        if(!portable_broadcast_pause(c))return false;
#endif
        c->policy=(telemetry_broadcast_policy_v1){.struct_size=sizeof(c->policy)};
        c->storage=(risc_runtime_capability_v1){.struct_size=sizeof(c->storage)};
        if(c->runtime->acquire(RISC_KEY_VALUE_CAPABILITY,1,1,&c->storage)) {
            const risc_key_value_v1 *kv=c->storage.api;uint8_t flags=0;
            c->policy.settings_valid=portable_broadcast_control_load(kv,&c->policy.enabled)&&portable_radio_load(kv,&flags);
            c->policy.radios_allowed=(flags&6u)==PORTABLE_RADIO_BLUETOOTH;
            if(!portable_broadcast_release_storage(c)){(void)portable_broadcast_pause(c);return false;}
        }
        if(!PORTABLE_BROADCAST_CUSTODY_SAFE())return false;
        c->loaded=true;c->loaded_at=health.uptime_ms;
    }
    return c->api->step(c->api->context,allow,&c->policy);
}
static inline bool portable_broadcast_set_enabled(portable_broadcast_client *c,bool enabled) {
    if(!c->api||!portable_broadcast_pause(c)||!portable_broadcast_release_storage(c))return false;
    c->policy=(telemetry_broadcast_policy_v1){.struct_size=sizeof(c->policy)};c->save_failed=true;
    c->storage=(risc_runtime_capability_v1){.struct_size=sizeof(c->storage)};
    bool saved=false;
    if(c->runtime->acquire(RISC_KEY_VALUE_CAPABILITY,1,1,&c->storage)) {
        const risc_key_value_v1 *kv=c->storage.api;
        if(pqa_preferences_valid(kv)) {
            uint8_t b[]={0x62,1,enabled?1:0,(uint8_t)((enabled?1:0)^0xa5u)};bool actual=false;
            int32_t rc=kv->put(kv->context,TELEMETRY_BROADCAST_KEY,b,sizeof(b));
            saved=(rc==RISC_KEY_VALUE_OK||rc==RISC_KEY_VALUE_IO)&&portable_broadcast_control_load(kv,&actual)&&actual==enabled;
        }
        if(!portable_broadcast_release_storage(c))return false;
    }
    if(!PORTABLE_BROADCAST_CUSTODY_SAFE())return false;
    c->save_failed=!saved;c->policy.enabled=saved&&enabled;c->policy.settings_valid=saved;c->loaded=false;
    bool safe=c->api->step(c->api->context,false,&c->policy);
    return saved&&safe;
}
static inline bool portable_broadcast_close(portable_broadcast_client *c,const risc_runtime_api_v1 *rt) {
    if(!portable_broadcast_release_storage(c))return false;
    if(c->grant.api&&!rt->release(&c->grant))return false;
    memset(c,0,sizeof(*c));return true;
}
/* The adapter owns the grant. Battery uses synchronous borrowed operations. */
bool portable_broadcast_status(telemetry_broadcast_status_v1 *out);
bool portable_broadcast_enable(bool enabled);
bool portable_broadcast_stop(void);
