#pragma once
#include "RiscRuntimeV1.h"
#include "RiscDisplayOutputV1.h"
#include "RiscBatteryGaugeV1.h"
/* Optional deployment-local app client hook, like PortableNavigation. It is
 * compiled only by an explicit target deployment. No device names, storage
 * privileges or firmware UI enter the generic adapter. Caller closes touch
 * subscriptions and holds no display lease; app RAM and grants remain live.
 * 1: woke, 0: ordinary refusal with display restored, -1: foreground failure.
 * -2: native retention; return immediately to Runtime without freeing state,
 * provider I/O, grant release or normal failure cleanup.
 * A retained native error is returned without provider restore/normal I/O;
 * the runtime's pre-fini barrier must retain the app and dependency graph. */
int portable_app_sleep(const risc_runtime_api_v1 *runtime,
                       const risc_display_output_api_v1 *display,
                       const risc_battery_gauge_api_v1 *gauge);

#ifdef PORTABLE_ALARM_CLIENT
#ifdef ALARM_SERVICE_TAGGED_V2
#include <AlarmServiceV2.h>
#else
#include "AlarmServiceV1.h"
#endif
/* Hidden application-local link, not a Runtime export/capability. Writers with
 * private grants use this only after a false poll to preserve native retention. */
bool portable_app_sleep_retained(void);
#ifdef PORTABLE_X4_IDLE_POLICY
/* Automatic idle always retains this app via reversible Light. */
int portable_app_idle_sleep(const risc_runtime_api_v1 *runtime,
                            const risc_display_output_api_v1 *display,
                            const risc_battery_gauge_api_v1 *gauge,
                            const alarm_service_v1 *alarms);
/* Private app-to-helper UI boundary, never a Runtime ABI. Begin runs only
 * after grants, neutral input, radios and the alarm ticket are ready, before
 * peripheral preparation. REFUSED means no image was changed. Once READY,
 * restore runs only after confirmed cleanup and grant release; any retained
 * result bypasses it. A later retained prepare can leave the pre-sleep image
 * physically visible: there is no legal post-retention repaint. */
typedef enum {
 PORTABLE_IDLE_UI_RETAINED=-2,
 PORTABLE_IDLE_UI_REFUSED=0,
 PORTABLE_IDLE_UI_READY=1
} portable_idle_ui_result;
typedef struct {
 void *context;
 portable_idle_ui_result (*begin)(void *);
 portable_idle_ui_result (*restore)(void *);
} portable_idle_sleep_ui;
int portable_app_idle_sleep_with_ui(const risc_runtime_api_v1 *runtime,
                                    const risc_display_output_api_v1 *display,
                                    const risc_battery_gauge_api_v1 *gauge,
                                    const alarm_service_v1 *alarms,
                                    const portable_idle_sleep_ui *ui);
#endif
/* Alarm-aware deployment hook consumes prepare_sleep immediately before entry.
 * Returning wake/refusal must reconcile again at the caller's safe point. */
int portable_app_alarm_sleep(const risc_runtime_api_v1 *runtime,
                            const risc_display_output_api_v1 *display,
                            const risc_battery_gauge_api_v1 *gauge,
                            const alarm_service_v1 *alarms);
#endif
