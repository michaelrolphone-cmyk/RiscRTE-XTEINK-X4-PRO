#pragma once
/* Settings owns the alarm service's namespace-1 preference, not its outputs or
 * occurrence records. This one-byte encoding is the Utilities alarm contract. */
#include "RiscKeyValueV1.h"
#include <stdbool.h>
#include <stdint.h>
#define PORTABLE_ALERT_VIBRATE 1u
#define PORTABLE_ALERT_SOUND 2u
#define PORTABLE_ALERT_BOTH 3u
#define PORTABLE_ALERT_KEY "alert_mode"
#define PORTABLE_ALERT_STORE_INSTANCE 1u
enum { PORTABLE_ALERT_LOADED=0, PORTABLE_ALERT_MISSING=1,
       PORTABLE_ALERT_INVALID=2, PORTABLE_ALERT_UNAVAILABLE=3 };
static inline bool portable_alert_api_valid(const risc_key_value_v1 *kv) {
    return kv && kv->api_version==RISC_KEY_VALUE_API_V1 &&
        kv->struct_size>=sizeof(*kv) && kv->get && kv->put;
}
static inline int portable_alert_load(const risc_key_value_v1 *kv,unsigned *mode) {
    if(!mode)return PORTABLE_ALERT_INVALID;
    *mode=0; /* Invalid/unreadable is never presented as a usable default. */
    if(!portable_alert_api_valid(kv))return PORTABLE_ALERT_UNAVAILABLE;
    uint8_t data=0;uint32_t size=0;
    int32_t rc=kv->get(kv->context,PORTABLE_ALERT_KEY,&data,sizeof(data),&size);
    if(rc==RISC_KEY_VALUE_NOT_FOUND) {
        *mode=PORTABLE_ALERT_VIBRATE;return PORTABLE_ALERT_MISSING;
    }
    if(rc==RISC_KEY_VALUE_BUFFER_SMALL)return PORTABLE_ALERT_INVALID;
    if(rc!=RISC_KEY_VALUE_OK)return PORTABLE_ALERT_UNAVAILABLE;
    if(size!=1 || data<PORTABLE_ALERT_VIBRATE || data>PORTABLE_ALERT_BOTH)
        return PORTABLE_ALERT_INVALID;
    *mode=data;return PORTABLE_ALERT_LOADED;
}
static inline bool portable_alert_save(const risc_key_value_v1 *kv,unsigned mode) {
    if(!portable_alert_api_valid(kv) || mode<PORTABLE_ALERT_VIBRATE || mode>PORTABLE_ALERT_BOTH)
        return false;
    const uint8_t data=(uint8_t)mode;
    int32_t rc=kv->put(kv->context,PORTABLE_ALERT_KEY,&data,sizeof(data));
    /* IO is uncertain: a commit can have succeeded. Exact reread, including
     * after OK, is the only success criterion; no prior-value assumption. */
    if(rc!=RISC_KEY_VALUE_OK && rc!=RISC_KEY_VALUE_IO)return false;
    unsigned actual;
    return portable_alert_load(kv,&actual)==PORTABLE_ALERT_LOADED && actual==mode;
}
static inline const char *portable_alert_name(unsigned mode) {
    return mode==PORTABLE_ALERT_VIBRATE?"Vibrate":mode==PORTABLE_ALERT_SOUND?"Sound":
        mode==PORTABLE_ALERT_BOTH?"Both":"Invalid";
}
