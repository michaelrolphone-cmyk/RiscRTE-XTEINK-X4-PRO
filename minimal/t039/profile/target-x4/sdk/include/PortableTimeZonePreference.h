#ifndef PORTABLE_TIMEZONE_PREFERENCE_H
#define PORTABLE_TIMEZONE_PREFERENCE_H
#include "PortableTimeZone.h"
#include "RiscKeyValueV1.h"
#ifdef __cplusplus
extern "C" {
#endif
/* App-owned namespace 1 only. This helper does not acquire a grant and cannot
 * verify its instance; callers must supply the existing instance-1 KV table. */
#define PORTABLE_TIMEZONE_STORE_INSTANCE 1u
#define PORTABLE_TIMEZONE_KEY "time_zone"
#define PORTABLE_TIMEZONE_RECORD_BYTES 44u
enum {
    PORTABLE_TIMEZONE_LOADED=0, PORTABLE_TIMEZONE_MISSING=1,
    PORTABLE_TIMEZONE_INVALID_RECORD=2, PORTABLE_TIMEZONE_UNAVAILABLE=3
};
enum {
    PORTABLE_TIMEZONE_SAVED=0, PORTABLE_TIMEZONE_UNCHANGED=1,
    PORTABLE_TIMEZONE_VIRTUAL_DEFAULT=2,
    PORTABLE_TIMEZONE_SAVE_INVALID=-1, PORTABLE_TIMEZONE_SAVE_UNAVAILABLE=-2,
    PORTABLE_TIMEZONE_WRITE_FAILED=-3, PORTABLE_TIMEZONE_VERIFY_FAILED=-4
};
/* Output is always a canonical ID (safe UTC fallback), unless out is NULL.
 * Loading NEVER writes. MISSING is a virtual UTC default, not persisted UTC. */
int portable_timezone_preference_load(const risc_key_value_v1 *kv,char out[PORTABLE_TIMEZONE_ID_BYTES]);
/* Explicit confirmed selection only; it may replace invalid storage, including
 * with UTC. Loading never repairs. An unchanged missing UTC is reported as
 * VIRTUAL_DEFAULT. A write must return OK AND exact readback must verify it;
 * IO-after-commit is a failure, with persistence deliberately left uncertain. */
int portable_timezone_preference_save(const risc_key_value_v1 *kv,const char *id,size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
