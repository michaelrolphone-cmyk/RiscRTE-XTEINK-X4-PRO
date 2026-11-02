#pragma once
#include "X4PowerDeepV1.h"
#define X4_POWER_COORDINATION_MAX_LOCKS 2u
#define X4_POWER_COORDINATION_TAG UINT32_C(0x58344331)
/* Append-only, provider-owned owner/reentry coordination. No hardware access,
 * raw native tokens, or ownership is delegated. Borrowed table is valid only
 * while the x4.power dependency remains pinned. Destroy every created token
 * before quiescence; failed cleanup requires retaining the dependency. */
/* Narrow coordination ABI, NOT platform.sync. Any failed mutating operation
 * may have committed state before a native unlock failure; consumers must
 * retain all tokens/dependencies on uncertainty and never retry cleanup.
 * is_owner is false after terminal custody. Clean refusal before acquisition
 * does not grant authority. Physical provider quiescence remains blocked. */
typedef struct {
 uint32_t api_version,struct_size;
 void *context;
 bool (*is_owner)(void*);
 bool (*create)(void*,uint64_t*);
 bool (*try_lock)(void*,uint64_t);
 bool (*unlock)(void*,uint64_t);
 bool (*destroy)(void*,uint64_t);
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
  s&&s->api_version==1&&s->struct_size>=sizeof(*s)&&s->is_owner&&s->create&&s->try_lock&&s->unlock&&s->destroy?s:NULL;
}
