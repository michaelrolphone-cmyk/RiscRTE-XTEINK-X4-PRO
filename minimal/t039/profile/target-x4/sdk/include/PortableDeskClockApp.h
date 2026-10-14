#pragma once
/* Private compile-time app/deployment links. Never native Runtime exports. */
#include "PortableDeskClock.h"
#include "RiscRuntimeV1.h"
#ifdef ALARM_SERVICE_TAGGED_V2
#include <AlarmServiceV2.h>
#else
#include "AlarmServiceV1.h"
#endif
#include "RiscDisplayOutputV1.h"
typedef struct {
 void *context;
 /* 0: continue; 1: ordinary cancellation; -2: retained. No subscription. */
 int (*cancelled)(void *context);
 /* 1: staged in RAM; 0: ordinary refusal; -2: retained. Must run before
  * provider preparation/holds: Runtime deliberately rejects staging then. */
 int (*stage)(void *context,const portable_desk_record *);
 /* 1: prepared; 0: ordinary refusal ALREADY rolled back; -2: retained. */
 int (*prepare)(void *context);
 /* 1: restored, including brightness; -2: unconfirmed custody, stop all I/O. */
 int (*resume)(void *context);
 /* Terminal entry for the same already-staged proposal. Success never
  * returns. 0: refusal, caller resumes before clearing; -2: no cleanup. */
 int (*stage_enter)(void *context,const portable_desk_record *,uint32_t sleep_ms,
                    uint32_t sampled_at_ms);
} portable_desk_sleep_ops;
/* Deployment reads owned Runtime record only during app_main. Returns 1 for
 * valid classified timer wake, 0 otherwise, -2 for retained grant cleanup. */
int portable_desk_clock_boot_read(const risc_runtime_api_v1 *,portable_desk_record *);
/* Called by the selected deployment local-sleep hook, inside adapter lifecycle.
 * 0 returns to ordinary Clock; -2 preserves all grants/resources. */
int portable_desk_clock_run(const risc_runtime_api_v1 *,const portable_desk_sleep_ops *);
/* App-local adapter helpers, only linked for this explicit build. */
bool portable_desk_adapter_sleep(void);
/* Seed returns1 on success,0 if unavailable,-2 on uncertain provider failure. */
int portable_desk_adapter_seed(void);
void portable_desk_adapter_begin(void);
bool portable_desk_adapter_flip(unsigned value);
void portable_desk_adapter_caption(int y,const char *text);
bool portable_desk_adapter_present(bool full);
void portable_desk_adapter_invalidate(void);
bool portable_desk_adapter_ready(void);
void portable_desk_adapter_retain(void);
void portable_desk_clock_refused(void);
void portable_desk_clock_radios_off(void);
/* Defer optional radio policy application until normal foreground is needed. */
int portable_desk_clock_mode(void);
bool portable_desk_adapter_foreground(void);

#ifdef PORTABLE_DESK_CLOCK_SPARSE_START
/* Pure cached classification from the existing boot_read; no extra native read. */
bool portable_desk_clock_boot_is_cold(void);
bool portable_desk_clock_boot_is_interactive(void);
/* Selected deployment only: module init is software-only. Call start in
 * app_main after classifying the boot. TIMER keeps display and alarm.service
 * (including its required closure), never direct input/battery/RTC or radios. */
enum { PORTABLE_DESK_START_TIMER=1, PORTABLE_DESK_START_FOREGROUND=2 };
/* 1: started/already in that mode; 0: refused or clean failure; -2: retained.
 * A clean failure permits finalization only; a refusal has no side effect. */
int portable_desk_adapter_start(unsigned mode);
/* Caller has already promoted the Runtime cohort. Only OK=0/ALREADY_READY=1
 * is accepted. No promotion grant is acquired here. Require no live frame and
 * a settled display; successful upgrade preserves mapping/history and is
 * one-way. RETAINED=-4 fences immediately. Same return contract as start. */
int portable_desk_adapter_upgrade(int32_t promotion_status);
/* Pure mode query for the coordinated app-local sleep hook. Never evidence
 * of arbitrary providers' inactivity, and never an authority to skip holds. */
bool portable_desk_adapter_timer_only(void);
/* Foreground toolbar/Quick Actions use the Clock's native UTC/timezone client,
 * never a second direct RTC calendar path. No live grant escapes this call. */
bool portable_desk_clock_time(uint8_t *hour,uint8_t *minute);
#endif

#ifdef PORTABLE_DESK_LOCK_HOME
/* Selected X4 Home policy only; no Runtime exports or new pin authority. */
bool portable_desk_clock_request_lock(bool enabled);
bool portable_desk_clock_lock_requested(void);
bool portable_desk_adapter_landscape(bool landscape,unsigned direction);
#endif
