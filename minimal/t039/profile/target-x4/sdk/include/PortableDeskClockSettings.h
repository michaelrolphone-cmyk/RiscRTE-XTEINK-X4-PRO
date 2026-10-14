#pragma once
/* App-owned namespace-1 preference. No authority to enter sleep is conveyed. */
#include "PortableDeskClock.h"
#include "PortableSleepPolicy.h"
#define PORTABLE_DESK_FACE_KEY "desk_clock_face"
#define PORTABLE_DESK_FACE_STORE_INSTANCE PORTABLE_SLEEP_STORE_INSTANCE
#define PORTABLE_DESK_FACE_RECORD_BYTES 4u
#ifdef PORTABLE_DESK_POINTS_FACE
#define PORTABLE_DESK_FACE_DEFAULT PORTABLE_DESK_POINTS
#else
#define PORTABLE_DESK_FACE_DEFAULT PORTABLE_DESK_SEGMENTS
#endif
enum { PORTABLE_DESK_FACE_LOADED=0, PORTABLE_DESK_FACE_MISSING=1,
       PORTABLE_DESK_FACE_INVALID=2, PORTABLE_DESK_FACE_UNAVAILABLE=3 };
static inline const char *portable_desk_face_name(unsigned face) {
    static const char *const names[]={"Segments","Sans","Serif","Minimal","Railway","Deco"
#ifdef PORTABLE_DESK_POINTS_FACE
    ,"Points in Time"
#endif
    };
    return face<PORTABLE_DESK_FACE_COUNT?names[face]:names[PORTABLE_DESK_SEGMENTS];
}
static inline int portable_desk_face_load(const risc_key_value_v1 *kv,unsigned *face) {
    if(!face)return PORTABLE_DESK_FACE_INVALID;
    *face=PORTABLE_DESK_FACE_DEFAULT;
    if(!portable_sleep_api_valid(kv))return PORTABLE_DESK_FACE_UNAVAILABLE;
    uint8_t bytes[PORTABLE_DESK_FACE_RECORD_BYTES]={0};uint32_t size=0;
    int32_t rc=kv->get(kv->context,PORTABLE_DESK_FACE_KEY,bytes,sizeof(bytes),&size);
    if(rc==RISC_KEY_VALUE_NOT_FOUND)return PORTABLE_DESK_FACE_MISSING;
    if(rc==RISC_KEY_VALUE_BUFFER_SMALL)return PORTABLE_DESK_FACE_INVALID;
    if(rc!=RISC_KEY_VALUE_OK)return PORTABLE_DESK_FACE_UNAVAILABLE;
    if(size!=sizeof(bytes) || bytes[0]!=0x46 || bytes[1]!=1 || bytes[2]>=PORTABLE_DESK_FACE_COUNT ||
       bytes[3]!=(uint8_t)(bytes[2]^0xa5u))return PORTABLE_DESK_FACE_INVALID;
    *face=bytes[2];return PORTABLE_DESK_FACE_LOADED;
}
static inline bool portable_desk_face_save(const risc_key_value_v1 *kv,unsigned face) {
    if(!portable_sleep_api_valid(kv) || face>=PORTABLE_DESK_FACE_COUNT)return false;
    unsigned current;
    if(portable_desk_face_load(kv,&current)==PORTABLE_DESK_FACE_LOADED && current==face)return true;
    const uint8_t bytes[]={0x46,1,(uint8_t)face,(uint8_t)(face^0xa5u)};
    if(kv->put(kv->context,PORTABLE_DESK_FACE_KEY,bytes,sizeof(bytes))!=RISC_KEY_VALUE_OK)return false;
    return portable_desk_face_load(kv,&current)==PORTABLE_DESK_FACE_LOADED && current==face;
}

/* Desk-only landscape direction; independent of the foreground UI flip. */
#define PORTABLE_DESK_DIRECTION_KEY "desk_direction"
static inline int portable_desk_direction_load(const risc_key_value_v1 *kv,unsigned *direction) {
    if(!direction)return PORTABLE_DESK_FACE_INVALID;
    *direction=0;
    if(!portable_sleep_api_valid(kv))return PORTABLE_DESK_FACE_UNAVAILABLE;
    uint8_t bytes[4]={0};uint32_t size=0;
    int32_t rc=kv->get(kv->context,PORTABLE_DESK_DIRECTION_KEY,bytes,sizeof(bytes),&size);
    if(rc==RISC_KEY_VALUE_NOT_FOUND)return PORTABLE_DESK_FACE_MISSING;
    if(rc==RISC_KEY_VALUE_BUFFER_SMALL)return PORTABLE_DESK_FACE_INVALID;
    if(rc!=RISC_KEY_VALUE_OK)return PORTABLE_DESK_FACE_UNAVAILABLE;
    if(size!=sizeof(bytes)||bytes[0]!=0x44||bytes[1]!=1||bytes[2]>1u||
       bytes[3]!=(uint8_t)(bytes[2]^0xa5u))return PORTABLE_DESK_FACE_INVALID;
    *direction=bytes[2];return PORTABLE_DESK_FACE_LOADED;
}
static inline bool portable_desk_direction_save(const risc_key_value_v1 *kv,unsigned direction) {
    if(!portable_sleep_api_valid(kv)||direction>1u)return false;
    unsigned current;
    if(portable_desk_direction_load(kv,&current)==PORTABLE_DESK_FACE_LOADED&&current==direction)return true;
    const uint8_t bytes[]={0x44,1,(uint8_t)direction,(uint8_t)(direction^0xa5u)};
    if(kv->put(kv->context,PORTABLE_DESK_DIRECTION_KEY,bytes,sizeof(bytes))!=RISC_KEY_VALUE_OK)return false;
    return portable_desk_direction_load(kv,&current)==PORTABLE_DESK_FACE_LOADED&&current==direction;
}
