#pragma once
#include "PortableQuickActions.h"
#include "PortableQuickPreferences.h"
#include "PortableSleepPolicy.h"
#include "RiscRuntimeV1.h"
#include "RiscDisplayOutputV1.h"
/* One invocation-local session. No retained grants or app pointers. */
typedef struct {
 pqa_state ui;
 unsigned brightness,volume,restore_volume;
#ifdef PORTABLE_LOW_BATTERY
 uint32_t idle_ms,deep_ms;
#endif
#ifdef PORTABLE_PAPER_TRANSITIONS
 unsigned restore_brightness;
#endif
#ifdef PORTABLE_FRONTLIGHT_TONE
 unsigned tone; /* Last confirmed namespace-1 preference, including virtual default. */
 bool retained; /* A terminal provider/release failure forbids later session I/O. */
#endif
 bool loaded,hour_24,dnd_enabled;
} pqa_session;
void pqa_session_init(pqa_session *s);
bool pqa_session_load(pqa_session *s,const risc_runtime_api_v1 *rt);
/* Caller must be at a settled display/service boundary. False is a lifecycle
 * failure; ordinary failed saves are shown in ui.error_flags. alerts_changed signals
 * confirmed volume or DND changes so the caller refreshes alarm.service. */
bool pqa_session_apply(pqa_session *s,const risc_runtime_api_v1 *rt,const risc_display_output_api_v1 *display,uint32_t actions,bool *alerts_changed);
bool pqa_session_restore(const pqa_session *s,const risc_display_output_api_v1 *display);
#ifdef PORTABLE_FRONTLIGHT_TONE
/* Tone-only boot/wake hook. Call after load, at a settled provider boundary,
 * before further provider/focus activity. It never changes brightness or OFF.
 * False is terminal and requires the adapter to retain custody immediately. */
bool pqa_session_sync_tone(pqa_session *s,const risc_display_output_api_v1 *display);
#endif
#ifdef PORTABLE_PAPER_TRANSITIONS
/* Confirm loaded paper preferences with the provider before displaying them.
 * With PORTABLE_FRONTLIGHT_TONE, discover the optional suffix and apply only a
 * confirmed saved tone, before brightness. Call at a settled boundary after
 * interactive brightness restore, before focus/provider use. Use the tone-only
 * hook for cold boot or noninteractive wake that must preserve dark output.
 * False is terminal; the adapter must retain custody immediately. Legacy
 * tables omit tone. pqa_session_restore remains brightness-only. */
bool pqa_session_sync_brightness(pqa_session *s,const risc_display_output_api_v1 *display);
#endif
