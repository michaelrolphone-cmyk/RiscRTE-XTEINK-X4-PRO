#ifndef PORTABLE_REALTIME_CLIENT_H
#define PORTABLE_REALTIME_CLIENT_H
/* Opt-in app-local client. Requires the canonical Runtime 0.1.49 SDK header.
 * No default app activation, external RTC writes, storage, networking or libc
 * time imports. Use only synchronously inside this invocation's app_main. */
#include "RiscRuntimeV1.h"
#include "RiscRealtimeV1.h"
#include "PortableRtcBasis.h"
#include "PortableTimeZone.h"
#ifdef __cplusplus
extern "C" {
#endif
#define PORTABLE_REALTIME_MAX_EPOCH INT64_C(2147483647)
enum {
 PORTABLE_REALTIME_OK=0, PORTABLE_REALTIME_UNSET=1, PORTABLE_REALTIME_RECOVERED=2,
 PORTABLE_REALTIME_INVALID=-1, PORTABLE_REALTIME_UNAVAILABLE=-2,
 PORTABLE_REALTIME_MALFORMED=-3, PORTABLE_REALTIME_CONTEXT=-4,
 PORTABLE_REALTIME_IO=-5, PORTABLE_REALTIME_UNCERTAIN=-6,
 PORTABLE_REALTIME_RETAINED=-7, PORTABLE_REALTIME_DENIED=-8,
 PORTABLE_REALTIME_FOLD=-9, PORTABLE_REALTIME_GAP=-10,
 PORTABLE_REALTIME_RANGE=-11, PORTABLE_REALTIME_BASIS_CHOICE=-12,
 PORTABLE_REALTIME_UNUSABLE=-13, PORTABLE_REALTIME_VERIFY=-14
};
enum { PORTABLE_REALTIME_READER=0, PORTABLE_REALTIME_CONTROL=1 };
enum { PORTABLE_REALTIME_TIMER_ONLY=0, PORTABLE_REALTIME_NORMAL_START=1 };
enum { PORTABLE_REALTIME_GUARD_UNCONFIRMED=0, PORTABLE_REALTIME_GUARD_SAFE=1,
       PORTABLE_REALTIME_GUARD_RETAINED=2 };
/* Pure app-local phase/permission check, never provider/broker I/O. SAFE means
 * the caller permits I/O in its current app_main foreground phase, before
 * device holds, with no known retention or ownership uncertainty. This is not
 * proof of Runtime ownership/storage safety; the broker/CPU remain authoritative.
 * No private Runtime API is needed. Checked before AND after every external call. A non-SAFE result is
 * sticky: no further I/O or release, even if a later guard would say SAFE. */
typedef int (*portable_realtime_phase_guard)(void *context);
/* Private implementation fields. Zero-initialize, do not copy/mutate/persist.
 * Keep the object and guard context alive through the invocation. */
typedef struct portable_realtime_client {
 const struct portable_realtime_client *self;
 portable_realtime_phase_guard guard;
 void *guard_context;
 bool (*acquire)(const char *,uint32_t,uint64_t,risc_runtime_capability_v1 *);
 bool (*release)(risc_runtime_capability_v1 *);
 risc_runtime_capability_v1 realtime_grant,rtc_grant;
 void *native_context;
 int32_t (*native_read)(void *,risc_realtime_snapshot_v1 *);
 int32_t (*native_seed)(void *,int64_t,uint32_t);
 int state,halt_reason,access,startup;
} portable_realtime_client;
typedef struct {
 uint64_t rtc_instance; /* Exact declared instance; zero requires uniqueness. */
 portable_timezone_rule rule; /* Caller-parsed/tested rule, no global TZ. */
 portable_rtc_basis basis; /* Caller-loaded/explicit metadata, never loaded here. */
 int fold_choice; /* -1 = reject ambiguity, 0 = earlier, 1 = later. */
 bool allow_basis_change; /* Explicitly allow reference-based interpretation. */
} portable_realtime_recovery_policy;
typedef struct {
 int reason; /* Operation result before cleanup; return may instead be UNCERTAIN. */
 int cleanup; /* OK or sticky guard/release failure. */
 int timezone_status;
 bool interpreted,seeded;
 portable_timezone_rtc_result interpretation; /* No persistence is implied. */
 risc_realtime_snapshot_v1 snapshot;
} portable_realtime_recovery_result;
typedef struct { int64_t epoch_seconds; uint32_t nanoseconds; } portable_realtime_estimate;
typedef struct {
 bool attempted,seeded,verified;
 risc_realtime_snapshot_v1 snapshot;
} portable_realtime_seed_result;
/* Explicit user-confirmed whole-second seed. CONTROL/NORMAL_START only; no
 * RTC/storage I/O. Requires no live RTC grant. Readback must be VALID and fall
 * within [epoch, epoch + budget_us]; budget is caller-selected, at most 5s.
 * IO may invalidate native time. No retry/rollback. attempted distinguishes a
 * possibly changed clock; seeded confirms only the seed callback's OK result,
 * verified confirms the bounded readback. CONTEXT/uncertainty is sticky. */
int portable_realtime_seed_confirmed(portable_realtime_client *,int64_t epoch,
 uint32_t budget_us,portable_realtime_seed_result *);
/* Open acquires only one fresh native grant; it neither reads nor seeds time.
 * A clean close allows reopen; a halted client cannot reopen. */
int portable_realtime_open(portable_realtime_client *,const risc_runtime_api_v1 *,
 int access,int startup,portable_realtime_phase_guard,void *guard_context);
/* Output is unchanged on negative status. UNSET is explicit and copied. */
int portable_realtime_read(portable_realtime_client *,risc_realtime_snapshot_v1 *);
/* Explicit normal-start/control-only recovery. Valid native time returns OK
 * without RTC acquisition. UNSET timer/read-only clients return DENIED.
 * An unsuccessful RTC acquire is UNCERTAIN: bool cannot certify rollback.
 * A false RTC read also halts as UNCERTAIN (reason IO), preserving both grants.
 * RTC is always safely released before checked native seed(whole_seconds,0).
 * A local-calendar gap/unchosen fold never silently falls back to UTC. */
int portable_realtime_recover_rtc(portable_realtime_client *,
 const portable_realtime_recovery_policy *,portable_realtime_recovery_result *);
/* Idempotent clean close. A failed release is never retried. */
int portable_realtime_close(portable_realtime_client *);
/* Pure sticky stop: call before holds/retention; does not attempt cleanup.
 * Prefer clean close BEFORE preparation. Never use close after device holds. */
void portable_realtime_stop(portable_realtime_client *,bool retained);
/* Pure estimate from an already validated sample and a bounded same-boot
 * elapsed duration supplied by the caller. Never a deep-sleep clock substitute;
 * never subtract boot-local counters from different boots. max_elapsed_us is
 * the app's processing budget, not a requested sleep duration. No native I/O. */
int portable_realtime_project(const risc_realtime_snapshot_v1 *,uint32_t elapsed_us,
 uint32_t max_elapsed_us,portable_realtime_estimate *);
#ifdef __cplusplus
}
#endif
#endif
