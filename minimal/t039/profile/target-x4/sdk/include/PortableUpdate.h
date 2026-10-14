#pragma once
#include <stdbool.h>
bool portable_update_services_safe(void);
bool portable_update_suspend(void);
void portable_update_resume(void);
bool portable_update_close(void);

#ifdef PORTABLE_BLE_BROADCAST
/* Pure app state: no status, network, bank or storage calls. */
bool portable_update_broadcast_safe(void);
#endif
bool portable_update_idle_ready(void);
