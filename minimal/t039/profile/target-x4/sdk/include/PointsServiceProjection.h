#ifndef UTILITIES_POINTS_SERVICE_PROJECTION_H
#define UTILITIES_POINTS_SERVICE_PROJECTION_H
#include "AlarmServiceV2.h"
#include "PointsCatalogProjection.h"
#define POINTS_SERVICE_PROJECTION_TAG UINT32_C(0x50545032)
#define POINTS_SERVICE_PROJECTION_VERSION 1u
typedef struct {uint32_t tag,version;int32_t (*projection)(void *,points_catalog_projection *);} points_service_projection_suffix;
typedef struct {alarm_service_sleep_v1 base;points_service_projection_suffix points;} points_service_v1;
typedef struct {alarm_service_descriptor_v2 base;points_service_projection_suffix points;} points_service_v2;
static inline int32_t points_service_project(const alarm_service_v1 *api,points_catalog_projection *out) {
    if(!api||!out||out->struct_size<sizeof(*out))return ALARM_INVALID;
    const points_service_projection_suffix *p=NULL;
    if(api->api_version==1&&api->struct_size>=sizeof(points_service_v1))p=&((const points_service_v1 *)api)->points;
    else if(alarm_service_descriptor(api)&&api->struct_size>=sizeof(points_service_v2))p=&((const points_service_v2 *)api)->points;
    return p&&p->tag==POINTS_SERVICE_PROJECTION_TAG&&p->version==POINTS_SERVICE_PROJECTION_VERSION&&p->projection?
        p->projection(api->context,out):ALARM_INVALID;
}
#endif
