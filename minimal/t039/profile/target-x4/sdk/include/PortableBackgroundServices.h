#pragma once
#include <stdbool.h>
/* Cleanup order is shared by ordinary app storage, sleep and error paths.
 * A refused cleanup permits no unrelated provider call after that point. */
#ifdef PORTABLE_CONTEXTS_CLIENT
bool portable_contexts_stop(void);
#endif
#ifdef PORTABLE_BLE_BROADCAST
bool portable_broadcast_stop(void);
#endif
static inline bool portable_background_stop(void) {
#ifdef PORTABLE_CONTEXTS_CLIENT
    if(!portable_contexts_stop())return false;
#endif
#ifdef PORTABLE_BLE_BROADCAST
    if(!portable_broadcast_stop())return false;
#endif
    return true;
}
