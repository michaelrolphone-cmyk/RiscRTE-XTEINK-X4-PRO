#pragma once
/* Hidden app-local fence. Requires the complete canonical Runtime header.
 * On success the invocation and all owned resources remain pinned. No provider
 * operation, polling, rendering or cleanup is allowed afterward. */
void portable_adapter_retain(void);
#ifdef PORTABLE_ALARM_TERMINAL_RETENTION
#include <stdbool.h>
/* Terminal service results permit no stage diagnostic before the fence. */
void portable_adapter_retain_silent(void);
bool portable_adapter_retained(void);
#endif
#ifdef PORTABLE_STAGE_LOGS
/* Plain first-cause input diagnostic; NULL clears the repeated-loss latch. */
void portable_adapter_touch_issue(const char *operation, int status, int terminal);
#endif

#ifdef PORTABLE_NATIVE_TIME_TOOLBAR
#include <stdbool.h>
#include "RiscRuntimeV1.h"
/* Pure query for the app's local phase guard. No provider/runtime operation. */
bool portable_adapter_retained(void);
/* Native controller custody, preserving ordinary app radio link states. */
const risc_runtime_api_v1 *portable_app_custody_runtime(void);
#endif
