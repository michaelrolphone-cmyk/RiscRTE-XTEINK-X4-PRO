#pragma once
#include <stdbool.h>
/* App-local ownership boundary, never a Runtime export. Suspend is idempotent:
 * finish/cancel the app-owned operation and verify radio cleanup before returning
 * true. It must not resume on wake/modal dismissal. False retains invocation and
 * grants; no normal provider I/O may follow uncertain cleanup. */
bool portable_radio_suspend(void);
bool portable_radio_services_safe(void);
#ifdef PORTABLE_RADIO_CONTINUOUS_CAPTURE
bool portable_radio_capture_active(void);
#endif
