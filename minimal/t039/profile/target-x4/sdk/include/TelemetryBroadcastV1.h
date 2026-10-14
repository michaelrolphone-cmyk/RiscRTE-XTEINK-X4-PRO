#pragma once
#include "RiscTelemetryV1.h"
#define TELEMETRY_BROADCAST_CAPABILITY "telemetry.broadcast"
#define TELEMETRY_BROADCAST_KEY "ble_broadcast"
enum { TELEMETRY_BROADCAST_OFF, TELEMETRY_BROADCAST_BLE_OFF,
       TELEMETRY_BROADCAST_PAUSED, TELEMETRY_BROADCAST_STARTING,
       TELEMETRY_BROADCAST_LIVE, TELEMETRY_BROADCAST_RETRY,
       TELEMETRY_BROADCAST_SETTINGS_ERROR, TELEMETRY_BROADCAST_RETAINED };
typedef struct {
    uint32_t struct_size,state,fields,updates,omitted_fields;
    bool enabled,settings_valid,cleanup_pending,restore_failed;
} telemetry_broadcast_status_v1;
typedef struct {
    uint32_t struct_size;
    bool enabled,radios_allowed,settings_valid;
} telemetry_broadcast_policy_v1;
/* Ordinary provider-owned state, never an app callback or runtime policy.
 * Deployment opts into open supported values from its bound sensor source.
 * Apps load/save their existing shared preferences and pass copied policy.
 * A source lacking temperature never invents it. Packet omissions are reported.
 * step must run from every settled foreground client at least once per second.
 * allow=false and pause close RF before controls, competing BLE work or sleep.
 * false means cleanup remains owned: retain grants/code and retry cleanup only.
 * A successful ordinary app grant release does not pause a boot-session provider.
 * The service never opens app storage or retains a caller pointer.
 */
typedef struct {
    uint32_t api_version,struct_size;void *context;
    bool (*step)(void *,bool allow,const telemetry_broadcast_policy_v1 *);
    bool (*pause)(void *);
    bool (*status)(void *,telemetry_broadcast_status_v1 *);
    int32_t (*enumerate)(void *,uint32_t index,risc_telemetry_field_v1 *);
    int32_t (*read)(void *,uint32_t id,int32_t *value);
} telemetry_broadcast_v1;

#if UINTPTR_MAX == UINT32_MAX
#ifdef __cplusplus
static_assert(sizeof(telemetry_broadcast_status_v1)==24,"broadcast copied status ABI");
static_assert(sizeof(telemetry_broadcast_v1)==32,"broadcast service ABI");
#else
_Static_assert(sizeof(telemetry_broadcast_status_v1)==24,"broadcast copied status ABI");
_Static_assert(sizeof(telemetry_broadcast_v1)==32,"broadcast service ABI");
#endif
#endif
