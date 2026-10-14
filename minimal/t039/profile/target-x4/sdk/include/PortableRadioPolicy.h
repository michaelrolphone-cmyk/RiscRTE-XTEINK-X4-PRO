#pragma once
#include "PortableQuickPreferences.h"
#include "RiscRuntimeV1.h"
#define PORTABLE_RADIO_KEY "quick_radio"
#define PORTABLE_RADIO_WIFI 1u
#define PORTABLE_RADIO_BLUETOOTH 2u
#define PORTABLE_RADIO_AIRPLANE 4u
#define PORTABLE_RADIO_PREVIOUS_WIFI 8u
#define PORTABLE_RADIO_PREVIOUS_BLUETOOTH 16u
static inline bool portable_radio_decode(const uint8_t *b,uint32_t n,uint8_t *flags) {
 if(!b||!flags||n!=4||b[0]!=0x51||b[1]!=1||(b[2]&~31u)||b[3]!=(uint8_t)(b[2]^0xa5))return false;
 if((b[2]&PORTABLE_RADIO_AIRPLANE)&&(b[2]&3u))return false;
 *flags=b[2];return true;
}
enum { PORTABLE_RADIO_PERSISTED, PORTABLE_RADIO_DEFAULT, PORTABLE_RADIO_INVALID, PORTABLE_RADIO_UNAVAILABLE, PORTABLE_RADIO_BUSY };
static inline unsigned portable_radio_load_result(const risc_key_value_v1*kv,uint8_t*flags) {
 *flags=0;if(!pqa_preferences_valid(kv))return PORTABLE_RADIO_UNAVAILABLE;
 uint8_t b[4];uint32_t n=0;int32_t rc=kv->get(kv->context,PORTABLE_RADIO_KEY,b,sizeof(b),&n);
 if(rc==RISC_KEY_VALUE_BUSY)return PORTABLE_RADIO_BUSY;
 if(rc==RISC_KEY_VALUE_NOT_FOUND){*flags=PORTABLE_RADIO_WIFI;return PORTABLE_RADIO_DEFAULT;}
 if(rc!=RISC_KEY_VALUE_OK)return PORTABLE_RADIO_UNAVAILABLE;
 return portable_radio_decode(b,n,flags)?PORTABLE_RADIO_PERSISTED:PORTABLE_RADIO_INVALID;
}
static inline bool portable_radio_load(const risc_key_value_v1*kv,uint8_t*flags) {
 return portable_radio_load_result(kv,flags)<=PORTABLE_RADIO_DEFAULT;
}
static inline bool portable_radio_save(const risc_key_value_v1*kv,uint8_t flags) {
 if(!pqa_preferences_valid(kv))return false;
 uint8_t b[4]={0x51,1,flags,(uint8_t)(flags^0xa5)},check=0;
 if(!portable_radio_decode(b,sizeof(b),&check))return false;
 int32_t rc=kv->put(kv->context,PORTABLE_RADIO_KEY,b,sizeof(b));
 return (rc==RISC_KEY_VALUE_OK||rc==RISC_KEY_VALUE_IO)&&portable_radio_load(kv,&check)&&check==flags;
}
/* Compile-time opt-in for radio-consuming apps. Unknown policy fails closed;
 * missing is the pre-existing Wi-Fi-enabled default and causes no write. */
static inline bool portable_radio_wifi_allowed(const risc_runtime_api_v1*rt) {
 risc_runtime_capability_v1 g={.struct_size=sizeof(g)};uint8_t flags=0;
 if(!rt||!rt->acquire(RISC_KEY_VALUE_CAPABILITY,1,1,&g))return false;
 bool ok=portable_radio_load(g.api,&flags);
 return rt->release(&g)&&ok&&!!(flags&PORTABLE_RADIO_WIFI);
}

/* Native Wi-Fi distinguishes an explicit Off setting from an unreadable record.
 * Read once and always release the policy grant before returning a result. */
enum { PORTABLE_WIFI_POLICY_ALLOWED, PORTABLE_WIFI_POLICY_OFF, PORTABLE_WIFI_POLICY_UNAVAILABLE, PORTABLE_WIFI_POLICY_BUSY };
static inline unsigned portable_radio_wifi_permission(const risc_runtime_api_v1 *rt) {
 risc_runtime_capability_v1 g={.struct_size=sizeof(g)};uint8_t flags=0;
 if(!rt || !rt->acquire(RISC_KEY_VALUE_CAPABILITY,1,1,&g))return PORTABLE_WIFI_POLICY_UNAVAILABLE;
 unsigned loaded=portable_radio_load_result(g.api,&flags);
 bool released=rt->release(&g);
 if(released && loaded==PORTABLE_RADIO_BUSY)return PORTABLE_WIFI_POLICY_BUSY;
 if(!released || loaded>PORTABLE_RADIO_DEFAULT)return PORTABLE_WIFI_POLICY_UNAVAILABLE;
 return flags&PORTABLE_RADIO_WIFI?PORTABLE_WIFI_POLICY_ALLOWED:PORTABLE_WIFI_POLICY_OFF;
}
