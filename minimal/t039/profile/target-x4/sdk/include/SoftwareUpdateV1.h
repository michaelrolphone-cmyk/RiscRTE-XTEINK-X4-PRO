#pragma once
#include <stdbool.h>
#include <stdint.h>
#define SOFTWARE_UPDATE_API_V1 1u
#define SOFTWARE_UPDATE_FIRMWARE_CAPABILITY "software.update.firmware"
#define SOFTWARE_UPDATE_APPS_CAPABILITY "software.update.apps"
#define SOFTWARE_UPDATE_ROWS_MAX 128u
#define SOFTWARE_UPDATE_IDLE 0u
#define SOFTWARE_UPDATE_CATALOG 1u
#define SOFTWARE_UPDATE_LIST 2u
#define SOFTWARE_UPDATE_PREPARING 3u
#define SOFTWARE_UPDATE_DOWNLOAD 4u
#define SOFTWARE_UPDATE_VERIFYING 5u
#define SOFTWARE_UPDATE_READY 6u
#define SOFTWARE_UPDATE_ACTIVATED 7u
#define SOFTWARE_UPDATE_ERROR 8u
#define SOFTWARE_UPDATE_RETAINED 9u
#define SOFTWARE_UPDATE_ACTIVATION_UNKNOWN 10u
#define SOFTWARE_UPDATE_AVAILABLE 0u
#define SOFTWARE_UPDATE_CURRENT 1u
#define SOFTWARE_UPDATE_UNSUPPORTED 2u
#define SOFTWARE_UPDATE_USB_ONLY 3u
/* Catalog metadata is display/selection only. Native bank owner independently
 * checks SHA, ELF admission, existing boot identity and unchanged authority. */
typedef struct {
 uint32_t struct_size, availability, size;
 char id[65], version[32], installed[32], reason[80];
} software_update_row_v1;
typedef struct {
 uint32_t struct_size,state,count,done,total;
 int32_t error;
 bool resources_open;
} software_update_status_v1;
typedef struct {
 uint32_t api_version,struct_size;
 void *context;
 bool (*refresh)(void*,uint64_t utc_seconds);
 bool (*step)(void*);
 bool (*status)(void*,software_update_status_v1*);
 bool (*get)(void*,uint32_t,software_update_row_v1*);
 /* UI must obtain a fresh explicit confirmation for this exact selected row. */
 bool (*begin)(void*,uint32_t,uint64_t utc_seconds);
 /* True only after transport AND unactivated bank transaction are closed. */
 bool (*cancel)(void*);
 /* Close network/radio before activate. READY means verified, not installed. */
 bool (*activate)(void*);
 bool (*restart)(void*);
} software_update_v1;
