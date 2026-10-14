#ifndef PORTABLE_SET_TIME_H
#define PORTABLE_SET_TIME_H
/* Opt-in user-confirmed Set Time. No boot policy, timezone mutation, migration,
 * chip policy, privileged imports, automatic retry, or transaction atomicity. */
#include "PortableRealtimeClient.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
 portable_timezone_rule rule; /* Explicit caller-selected timezone. */
 portable_timezone_civil local; /* Desired LOCAL fields; weekday is ignored. */
 portable_rtc_basis basis; /* Loaded/explicit choice; never inferred here. */
 int fold_choice; /* -1 rejects ambiguity, 0 earlier, 1 later. */
 uint64_t rtc_instance; /* Declared RTC@2 instance; zero requires uniqueness. */
 uint32_t native_readback_budget_us; /* Explicit tolerance, 0..5 seconds. */
} portable_set_time_request;
typedef struct {
 int64_t utc_epoch;
 portable_timezone_civil rtc_calendar;
 portable_rtc_basis basis; /* Same stores_utc, reference set to utc_epoch. */
} portable_set_time_plan;
enum { PORTABLE_SET_TIME_NOT_ATTEMPTED=0, PORTABLE_SET_TIME_UNCONFIRMED=1,
       PORTABLE_SET_TIME_CONFIRMED=2 };
enum { PORTABLE_SET_TIME_PLAN=0, PORTABLE_SET_TIME_RTC_ACQUIRE,
 PORTABLE_SET_TIME_RTC_BEFORE, PORTABLE_SET_TIME_RTC_WRITE, PORTABLE_SET_TIME_RTC_VERIFY,
 PORTABLE_SET_TIME_RTC_AFTER, PORTABLE_SET_TIME_RTC_RELEASE,
 PORTABLE_SET_TIME_NATIVE, PORTABLE_SET_TIME_KV_ACQUIRE, PORTABLE_SET_TIME_KV_WRITE,
 PORTABLE_SET_TIME_KV_VERIFY, PORTABLE_SET_TIME_KV_RELEASE, PORTABLE_SET_TIME_DONE };
typedef struct {
 int reason,cleanup,stage; /* reason survives a cleanup failure. */
 int rtc_outcome,metadata_outcome;
 bool planned,rtc_write_accepted,metadata_write_accepted;
 bool rtc_window_confirmed,rtc_tick_accepted;
 uint64_t rtc_window_us; /* Full native monotonic bracket, <=250000 on success. */
 int64_t verified_utc_epoch; /* Requested instant or verified single tick +1. */
 portable_set_time_plan plan;
 portable_realtime_seed_result native;
} portable_set_time_result;
/* Private fields. Zero-initialize, never copy/mutate/persist, invocation-local.
 * Preserve this object/context on uncertainty. The controller must invoke its
 * Runtime retention fence before returning; helper return alone pins nothing. */
typedef struct portable_set_time_client {
 const struct portable_set_time_client *self;
 portable_realtime_client realtime;
 portable_realtime_phase_guard guard;
 void *guard_context;
 bool (*acquire)(const char *,uint32_t,uint64_t,risc_runtime_capability_v1 *);
 bool (*release)(risc_runtime_capability_v1 *);
 risc_runtime_capability_v1 rtc_grant,kv_grant;
 int state,halt_reason;
} portable_set_time_client;
/* Pure. Fails without altering out on gap, unchosen fold, invalid fields/rule,
 * native-2038 range, RTC calendar outside 2000..2099 or reference out of range. */
int portable_set_time_prepare(const portable_set_time_request *,portable_set_time_plan *out);
/* Open obtains native CONTROL only. It does not read or write any clock/KV. */
int portable_set_time_open(portable_set_time_client *,const risc_runtime_api_v1 *,
 portable_realtime_phase_guard,void *guard_context);
/* Call ONLY for an explicit confirmed Set Time action. Each call is a new
 * user action, never an automatic retry. RTC readback (exact or a single calendar
 * tick proven within 250ms by native monotonic brackets) precedes RTC release,
 * bounded native seed/readback, and explicit namespace-1 rtc_basis put/get.
 * Partial outcomes are independent: errors do not roll back changed clocks/KV.
 * Any false RTC call/uncertain provider operation permanently stops all I/O,
 * including cleanup. Documented KV IO/INVALID/NOT_FOUND/BUFFER_SMALL errors
 * keep metadata unconfirmed, release the KV grant with phase checks and permit
 * a new explicit attempt only after clean release. No readback follows a failed
 * put. CONTEXT/unknown KV results still halt. Known native IO permits explicit retry but invalidates
 * previous clock assumptions. A clean verification mismatch permits retry. */
int portable_set_time_apply_confirmed(portable_set_time_client *,
 const portable_set_time_request *,portable_set_time_result *);
int portable_set_time_close(portable_set_time_client *);
void portable_set_time_stop(portable_set_time_client *,bool retained);
#ifdef __cplusplus
}
#endif
#endif
