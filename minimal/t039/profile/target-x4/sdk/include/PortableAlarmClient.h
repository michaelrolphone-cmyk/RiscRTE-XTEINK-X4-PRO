#pragma once
#ifdef PORTABLE_ALARM_TERMINAL_RETENTION
#include "PortableAlarmTerminalClient.h"
#else
/* Optional Utilities service consumer. No schedule, RTC or output policy here.
 * Every normal call belongs to the foreground serialized settled-frame point.
 * A failed/pending presentation permits only failure_stop, never pump. */
#ifdef ALARM_SERVICE_TAGGED_V2
#include <AlarmServiceV2.h>
#else
#include "AlarmServiceV1.h"
#endif
#include "RiscRuntimeV1.h"
#include <string.h>
#ifdef PORTABLE_NATIVE_CUSTODY_FENCE
#include "PortableNativeCustody.h"
#endif
typedef struct {
    risc_runtime_capability_v1 grant;
    const alarm_service_v1 *api;
    alarm_status_v1 status;
#ifdef ALARM_SERVICE_TAGGED_V2
    bool retained;
#endif
} portable_alarm_client;
static inline bool portable_alarm_open(portable_alarm_client *c,const risc_runtime_api_v1 *r) {
    memset(c,0,sizeof(*c));c->grant.struct_size=sizeof(c->grant);
#ifdef ALARM_SERVICE_TAGGED_V2
    if(!r->acquire(ALARM_SERVICE_CAPABILITY,ALARM_SERVICE_API_V2,0,&c->grant))return false;
#else
    if(!r->acquire(ALARM_SERVICE_CAPABILITY,1,0,&c->grant))return false;
#endif
    const alarm_service_v1 *a=c->grant.api;
#ifdef ALARM_SERVICE_TAGGED_V2
    if(!alarm_service_descriptor(a))return false;
#else
    if(!a || a->api_version!=1 || a->struct_size<sizeof(*a) || !a->status || !a->step ||
       !a->refresh || !a->acknowledge || !a->prepare_sleep || !a->stop_only)return false;
#endif
    c->api=a;return true;
}
#ifdef ALARM_SERVICE_TAGGED_V2
/* Only explicit custody/output uncertainty pins resources. Typed storage/RTC
 * failures remain copied service states, so the foreground can show/retry them. */
static inline bool portable_alarm_result(portable_alarm_client *c,int32_t result) {
    if(result==ALARM_RETAINED || result==ALARM_OUTPUT ||
       result<ALARM_FOREGROUND || result>ALARM_PENDING) {
        c->retained=true;
#ifdef PORTABLE_NATIVE_CUSTODY_FENCE
        portable_adapter_retain();
#endif
        return false;
    }
    return true;
}
static inline bool portable_alarm_callable(const portable_alarm_client *c) {
    return !c->retained && alarm_service_descriptor(c->api)!=NULL;
}
static inline uint32_t portable_alarm_output_modes(const portable_alarm_client *c) {
    const alarm_service_descriptor_v2 *d=c->retained?NULL:alarm_service_descriptor(c->api);
    return d?d->output_modes:ALARM_MODE_VISUAL;
}
static inline bool portable_alarm_refresh(portable_alarm_client *c) {
    return portable_alarm_callable(c) && portable_alarm_result(c,c->api->refresh(c->api->context));
}
static inline bool portable_alarm_acknowledge(portable_alarm_client *c,const alarm_token_v1 *token) {
    return portable_alarm_callable(c) && portable_alarm_result(c,c->api->acknowledge(c->api->context,token));
}
#endif
static inline bool portable_alarm_status(portable_alarm_client *c) {
#ifdef ALARM_SERVICE_TAGGED_V2
    if(!portable_alarm_callable(c))return false;
    c->status=(alarm_status_v1){.struct_size=sizeof(c->status)};
    int32_t result=c->api->status(c->api->context,&c->status);
    if(!portable_alarm_result(c,result) || result!=ALARM_OK ||
       !portable_alarm_result(c,c->status.error))return false;
    return
#else
    c->status=(alarm_status_v1){.struct_size=sizeof(c->status)};
#ifdef PORTABLE_NATIVE_CUSTODY_FENCE
    if(!c->api)return false;
    if(c->api->status(c->api->context,&c->status)!=ALARM_OK) {portable_adapter_retain();return false;}
    return
#else
    return c->api && c->api->status(c->api->context,&c->status)==ALARM_OK &&
#endif
#endif
        c->status.api_version==1 && c->status.struct_size>=sizeof(c->status) &&
        c->status.state<=ALARM_STATE_CUE;
}
static inline bool portable_alarm_pump(portable_alarm_client *c) {
#ifdef ALARM_SERVICE_TAGGED_V2
    if(!portable_alarm_callable(c) || !portable_alarm_result(c,c->api->step(c->api->context)))return false;
#elif defined(PORTABLE_NATIVE_CUSTODY_FENCE)
    int32_t result=c->api->step(c->api->context);
    if(result!=ALARM_OK && result!=ALARM_PENDING){portable_adapter_retain();return false;}
#else
    (void)c->api->step(c->api->context);
#endif
    return portable_alarm_status(c);
}
static inline bool portable_alarm_owned(const portable_alarm_client *c) {
    return c->status.state==ALARM_STATE_CUE || c->status.occurrence.generation || c->status.output_uncertain ||
        c->status.state==ALARM_STATE_ALERT || c->status.state==ALARM_STATE_DISMISSING;
}
/* A cue reserves outputs but is not a foreground modal occurrence. */
static inline bool portable_alarm_cue(const portable_alarm_client *c) {
    return c->status.state==ALARM_STATE_CUE;
}
static inline bool portable_alarm_failure_stop(portable_alarm_client *c) {
#ifdef ALARM_SERVICE_TAGGED_V2
    if(c->retained)return false;
#endif
    if(!c->api)return true;
    int32_t result=ALARM_PENDING;
    /* Exactly three independent operations, never normal I/O or output start.
       Do not automatically repeat after an uncertain result. */
#ifdef ALARM_SERVICE_TAGGED_V2
    for(unsigned i=0;i<3 && result==ALARM_PENDING;i++) {
      if(!portable_alarm_callable(c))return false;
      result=c->api->stop_only(c->api->context);
      if(!portable_alarm_result(c,result))return false;
    }
#elif defined(PORTABLE_NATIVE_CUSTODY_FENCE)
    for(unsigned i=0;i<3 && result==ALARM_PENDING;i++) {
      result=c->api->stop_only(c->api->context);
      if(result!=ALARM_OK && result!=ALARM_PENDING){portable_adapter_retain();return false;}
    }
#else
    for(unsigned i=0;i<3 && result==ALARM_PENDING;i++)result=c->api->stop_only(c->api->context);
#endif
    return result==ALARM_OK;
}
static inline bool portable_alarm_close(portable_alarm_client *c,const risc_runtime_api_v1 *r) {
#ifdef ALARM_SERVICE_TAGGED_V2
    if(c->retained)return false;
#endif
    if(c->grant.api && !r->release(&c->grant))return false;
    memset(c,0,sizeof(*c));return true;
}

#endif
