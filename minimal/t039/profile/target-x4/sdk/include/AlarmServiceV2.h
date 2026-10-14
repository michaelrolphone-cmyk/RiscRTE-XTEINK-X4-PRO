#ifndef UTILITIES_ALARM_SERVICE_V2_H
#define UTILITIES_ALARM_SERVICE_V2_H
#include "AlarmServiceV1.h"
#define ALARM_MODE_VISUAL 0u
#define ALARM_RETAINED (-9)
/* Explicit capability negotiation is mandatory. Never inspect a v1 suffix:
 * published source lineages assign incompatible meanings to the same offset.
 * v2 retains the base field offsets and copied status/ticket contracts. */
#define ALARM_SERVICE_API_V2 2u
#define ALARM_SERVICE_DESCRIPTOR_TAG UINT32_C(0x414c4432)
#define ALARM_SERVICE_DESCRIPTOR_VERSION 1u
#define ALARM_DESCRIPTOR_RESUME_SLEEP 1u
typedef struct {
    alarm_service_v1 base;
    uint32_t tag, descriptor_version, output_modes, features;
    int32_t (*resume_sleep)(void *, const alarm_sleep_v1 *);
} alarm_service_descriptor_v2;
static inline const alarm_service_descriptor_v2 *alarm_service_descriptor(const alarm_service_v1 *s) {
    if(!s || s->api_version!=ALARM_SERVICE_API_V2 || s->struct_size<sizeof(alarm_service_descriptor_v2))return NULL;
    const alarm_service_descriptor_v2 *d=(const alarm_service_descriptor_v2 *)s;
    if(d->tag!=ALARM_SERVICE_DESCRIPTOR_TAG || d->descriptor_version!=ALARM_SERVICE_DESCRIPTOR_VERSION ||
       (d->output_modes&~ALARM_MODE_BOTH) || (d->features&~ALARM_DESCRIPTOR_RESUME_SLEEP) ||
       ((d->features&ALARM_DESCRIPTOR_RESUME_SLEEP)!=0)!=(d->resume_sleep!=NULL) ||
       !s->status || !s->step || !s->refresh || !s->acknowledge || !s->prepare_sleep || !s->stop_only)return NULL;
    return d;
}
/* Call only once after successful native Light return with the unchanged ticket.
 * Refused sleep must not consume this boundary. Descriptor validation precedes
 * every callback dispatch, including malformed/old providers. */
static inline int32_t alarm_service_resume(const alarm_service_v1 *s,const alarm_sleep_v1 *ticket) {
    const alarm_service_descriptor_v2 *d=alarm_service_descriptor(s);
    return d && d->resume_sleep ? d->resume_sleep(s->context,ticket) : ALARM_INVALID;
}
#if defined(__cplusplus)
static_assert(offsetof(alarm_service_descriptor_v2,tag)==sizeof(alarm_service_v1),"base prefix");
#else
_Static_assert(offsetof(alarm_service_descriptor_v2,tag)==sizeof(alarm_service_v1),"base prefix");
#endif
#if UINTPTR_MAX == UINT32_MAX
#if defined(__cplusplus)
static_assert(sizeof(alarm_service_descriptor_v2)==56,"tagged target ABI");
#else
_Static_assert(sizeof(alarm_service_descriptor_v2)==56,"tagged target ABI");
#endif
#endif
#endif
