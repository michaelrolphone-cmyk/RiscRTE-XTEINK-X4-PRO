#pragma once
/* Shared app-owned controls. These are namespace-1 preferences, not Runtime
 * settings or device ABI. Notification volume uses the existing alarm_volume
 * one-byte contract: absent means50%; zero mutes sound, never vibration. */
#include "RiscKeyValueV1.h"
#include <stdbool.h>
#include <stdint.h>
#define PQA_STORE_INSTANCE 1u
#define PQA_BRIGHTNESS_KEY "brightness"
#define PQA_RESTORE_BRIGHTNESS_KEY "quick_bright"
#define PQA_VOLUME_KEY "alarm_volume"
#define PQA_RESTORE_VOLUME_KEY "quick_volume"
#define PQA_DND_KEY "alert_dnd"
#define PQA_BRIGHTNESS_DEFAULT 40u
#define PQA_VOLUME_DEFAULT 50u
#ifdef PORTABLE_FRONTLIGHT_TONE
/* Dimensionless cool-to-warm ratio, independent of brightness and OFF. */
#define PQA_TONE_KEY "frontlight_tone"
#define PQA_TONE_DEFAULT 50u
#endif
static inline bool pqa_preferences_valid(const risc_key_value_v1 *kv) {
 return kv && kv->api_version==1 && kv->struct_size>=sizeof(*kv) && kv->get && kv->put;
}
/* Missing is a valid virtual default and never triggers an implicit write.
 * On malformed/unreadable storage, retain the supplied safe fallback but tell
 * the UI it is unconfirmed. Never present unknown state as persisted. */
static inline bool pqa_preference_load(const risc_key_value_v1 *kv,const char *key,unsigned fallback,unsigned minimum,unsigned *value) {
 *value=fallback;if(!pqa_preferences_valid(kv))return false;
 uint8_t data=0;uint32_t size=0;int32_t rc=kv->get(kv->context,key,&data,1,&size);
 if(rc==RISC_KEY_VALUE_NOT_FOUND)return true;
 if(rc!=RISC_KEY_VALUE_OK || size!=1 || data<minimum || data>100)return false;
 *value=data;return true;
}
static inline bool pqa_preference_save(const risc_key_value_v1 *kv,const char *key,unsigned value,unsigned minimum) {
 if(!pqa_preferences_valid(kv)||value<minimum||value>100)return false;
 const uint8_t byte=(uint8_t)value;int32_t rc=kv->put(kv->context,key,&byte,1);
 if(rc!=RISC_KEY_VALUE_OK && rc!=RISC_KEY_VALUE_IO)return false;
 uint8_t actual=255;uint32_t size=0;
 return kv->get(kv->context,key,&actual,1,&size)==RISC_KEY_VALUE_OK && size==1 && actual==value;
}

/* DND is an independent one-byte Boolean. Missing means off without a write.
 * Unavailable or malformed storage must never be rendered as confirmed state. */
static inline bool pqa_dnd_load(const risc_key_value_v1 *kv,bool *enabled) {
 *enabled=false;if(!pqa_preferences_valid(kv))return false;
 uint8_t byte=0;uint32_t size=0;int32_t rc=kv->get(kv->context,PQA_DND_KEY,&byte,1,&size);
 if(rc==RISC_KEY_VALUE_NOT_FOUND)return true;
 if(rc!=RISC_KEY_VALUE_OK || size!=1 || byte>1)return false;
 *enabled=byte!=0;return true;
}
static inline bool pqa_dnd_save(const risc_key_value_v1 *kv,bool enabled) {
 if(!pqa_preferences_valid(kv))return false;
 const uint8_t byte=enabled?1u:0u;
 int32_t rc=kv->put(kv->context,PQA_DND_KEY,&byte,1);
 if(rc!=RISC_KEY_VALUE_OK && rc!=RISC_KEY_VALUE_IO)return false;
 uint8_t actual=255;uint32_t size=0;
 return kv->get(kv->context,PQA_DND_KEY,&actual,1,&size)==RISC_KEY_VALUE_OK && size==1 && actual==byte;
}
