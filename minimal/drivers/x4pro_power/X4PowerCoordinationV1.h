#pragma once
#include "X4PowerDeepV1.h"
#define X4_POWER_COORDINATION_MAX_LOCKS 2u
#define X4_POWER_COORDINATION_TAG UINT32_C(0x58344331)
/* Append-only, provider-owned owner/reentry coordination. No hardware access,
 * raw native tokens, or ownership is delegated. Borrowed table is valid only
 * while the x4.power dependency remains pinned. Destroy every created token
 * before quiescence; failed cleanup requires retaining the dependency. */
#define X4_COORDINATION_OK 0
#define X4_COORDINATION_BUSY 1
#define X4_COORDINATION_INVALID (-1)
#define X4_COORDINATION_RETAINED (-9)
/* Narrow coordination ABI, NOT platform.sync. BUSY and INVALID leave logical state unchanged.
 * RETAINED may have committed state before native unlock failure; consumers
 * must retain all tokens/dependencies and never retry cleanup. Unknown results
 * are equally terminal. Physical provider quiescence remains blocked. */
typedef struct {
 uint32_t api_version,struct_size;
 void *context;
 int32_t (*owner)(void*);
 int32_t (*create)(void*,uint64_t*);
 int32_t (*try_lock)(void*,uint64_t);
 int32_t (*unlock)(void*,uint64_t);
 int32_t (*destroy)(void*,uint64_t);
} x4_power_coordination_api_v1;
typedef struct {
 x4_power_deep_v1 deep;
 uint32_t coordination_tag,coordination_version;
 const x4_power_coordination_api_v1 *coordination;
} x4_power_coordination_v1;
static inline const x4_power_coordination_api_v1 *x4_power_coordination(const x4_power_v1 *api){
 const x4_power_deep_v1 *deep=x4_power_deep(api);
 if(!deep||api->struct_size<sizeof(x4_power_coordination_v1))return NULL;
 const x4_power_coordination_v1 *ext=(const x4_power_coordination_v1*)api;
 const x4_power_coordination_api_v1 *s=ext->coordination;
 return ext->coordination_tag==X4_POWER_COORDINATION_TAG&&ext->coordination_version==1&&
  s&&s->api_version==1&&s->struct_size>=sizeof(*s)&&s->owner&&s->create&&s->try_lock&&s->unlock&&s->destroy?s:NULL;
}
