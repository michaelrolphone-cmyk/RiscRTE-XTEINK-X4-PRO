#pragma once
/* App-owned desk-clock policy, not a Runtime capability or sleep operation.
 * Native retained storage owns integrity, app/cohort binding and reset cause.
 * This payload contains no addresses, claims, grants or executable state. */
#include "PortableReaderPreferences.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define PORTABLE_DESK_CLOCK_RECORD_TYPE UINT32_C(0x44434c4b)
#ifdef PORTABLE_DESK_POINTS_SNAPSHOT
#include "PortableDeskPointsSnapshot.h"
#include "PortableTimeZone.h"
#define PORTABLE_DESK_CLOCK_RECORD_SCHEMA 3u
#define PORTABLE_DESK_CLOCK_RECORD_BYTES 408u
#else
#define PORTABLE_DESK_CLOCK_RECORD_SCHEMA 1u
#define PORTABLE_DESK_CLOCK_RECORD_BYTES 80u
#endif
#define PORTABLE_DESK_CLOCK_FULL_PERIOD 30u
#define PORTABLE_DESK_CLOCK_MAX_PRESENTS 3u
enum { PORTABLE_DESK_SEGMENTS, PORTABLE_DESK_SANS, PORTABLE_DESK_SERIF,
       PORTABLE_DESK_MINIMAL, PORTABLE_DESK_RAILWAY, PORTABLE_DESK_DECO,
#ifdef PORTABLE_DESK_POINTS_FACE
       PORTABLE_DESK_POINTS,
#endif
       PORTABLE_DESK_FACE_COUNT };
typedef struct {
    uint8_t face, time_format, language, flip_ui, rtc_stores_utc, rtc_variant;
    uint32_t rtc_reference_epoch;
    char time_zone[40];
#ifdef PORTABLE_DESK_POINTS_SNAPSHOT
    portable_desk_points_snapshot points;
#endif
} portable_desk_config;
typedef struct {
    portable_desk_config config;
    int64_t displayed_minute;
    uint8_t refresh_modulo;
    bool has_image;
} portable_desk_record;
typedef struct {
    portable_desk_record current;
    int64_t planned_minute;
    uint8_t attempts;
    bool active, pending, full;
} portable_desk_cycle;
typedef struct {
    int64_t minute, previous_minute;
    bool full, has_previous;
} portable_desk_frame;
enum { PORTABLE_DESK_STOP=-1, PORTABLE_DESK_REPAINT=0, PORTABLE_DESK_READY=1 };
static inline bool portable_desk_config_valid(const portable_desk_config *c) {
    if(!c || c->face>=PORTABLE_DESK_FACE_COUNT || c->time_format>1u ||
       c->language>=PORTABLE_READER_LANGUAGE_COUNT || c->flip_ui>1u || c->rtc_stores_utc>1u)return false;
#ifdef PORTABLE_DESK_POINTS_SNAPSHOT
    if(!portable_desk_points_valid(&c->points))return false;
#endif
    bool ended=false;
    for(unsigned i=0;i<sizeof(c->time_zone);++i){
        unsigned char b=(unsigned char)c->time_zone[i];
        if(ended && b)return false;
        if(!b)ended=true;
        else if(b<32u || b>126u)return false;
    }
    return ended;
}
static inline bool portable_desk_same_config(const portable_desk_config *a,const portable_desk_config *b) {
    return a->face==b->face && a->time_format==b->time_format && a->language==b->language &&
        a->flip_ui==b->flip_ui && a->rtc_stores_utc==b->rtc_stores_utc &&
        a->rtc_variant==b->rtc_variant && a->rtc_reference_epoch==b->rtc_reference_epoch &&
        !memcmp(a->time_zone,b->time_zone,sizeof(a->time_zone))
#ifdef PORTABLE_DESK_POINTS_SNAPSHOT
        && a->points.status==b->points.status &&
        (a->points.status!=PORTABLE_DESK_POINTS_READY || !memcmp(&a->points.view,&b->points.view,sizeof(a->points.view)))
#endif
        ;
}
/* 2^32 modulo 60 is 16. This fixed-width reduction avoids new 64-bit
 * compiler-helper imports in a freestanding Xtensa application. */
static inline uint32_t portable_desk_second_in_minute(int64_t seconds) {
    uint64_t value=(uint64_t)seconds;
    return ((((uint32_t)(value>>32)%60u)*16u)+((uint32_t)value%60u))%60u;
}
static inline bool portable_desk_record_valid(const portable_desk_record *r) {
    return r && portable_desk_config_valid(&r->config) && r->has_image &&
        r->displayed_minute>=0 && portable_desk_second_in_minute(r->displayed_minute)==0 &&
        r->refresh_modulo<PORTABLE_DESK_CLOCK_FULL_PERIOD;
}
static inline bool portable_desk_encode(const portable_desk_record *r,uint8_t *out,size_t size) {
    if(!out || size!=PORTABLE_DESK_CLOCK_RECORD_BYTES || !portable_desk_record_valid(r))return false;
    uint8_t bytes[PORTABLE_DESK_CLOCK_RECORD_BYTES]={0};
    memcpy(bytes,"DCLK",4);bytes[4]=PORTABLE_DESK_CLOCK_RECORD_SCHEMA;bytes[5]=1;
    bytes[6]=r->config.face;bytes[7]=r->config.time_format;bytes[8]=r->config.language;
    bytes[9]=r->config.flip_ui;bytes[10]=r->config.rtc_stores_utc;bytes[11]=r->config.rtc_variant;
    for(unsigned i=0;i<4;++i)bytes[12+i]=(uint8_t)(r->config.rtc_reference_epoch>>(8u*i));
    uint32_t low=(uint32_t)r->displayed_minute,high=(uint32_t)((uint64_t)r->displayed_minute>>32);
    for(unsigned i=0;i<4;++i){bytes[16+i]=(uint8_t)(low>>(8u*i));bytes[20+i]=(uint8_t)(high>>(8u*i));}
    bytes[24]=r->refresh_modulo;
#ifdef PORTABLE_DESK_POINTS_SNAPSHOT
    bytes[25]=r->config.points.status;memcpy(bytes+32,r->config.time_zone,40);
    if(!portable_desk_points_encode(&r->config.points,bytes+80))return false;
#else
    memcpy(bytes+32,r->config.time_zone,40);
#endif
    memcpy(out,bytes,sizeof(bytes));return true;
}
static inline bool portable_desk_decode(const uint8_t *bytes,size_t size,portable_desk_record *out) {
    if(!bytes || !out || size!=PORTABLE_DESK_CLOCK_RECORD_BYTES || memcmp(bytes,"DCLK",4) ||
       bytes[4]!=PORTABLE_DESK_CLOCK_RECORD_SCHEMA || bytes[5]!=1)return false;
#ifdef PORTABLE_DESK_POINTS_SNAPSHOT
    for(unsigned i=26;i<32;i++)if(bytes[i])return false;
    for(unsigned i=72;i<80;i++)if(bytes[i])return false;
#else
    for(unsigned i=25;i<32;++i)if(bytes[i])return false;
    for(unsigned i=72;i<80;++i)if(bytes[i])return false;
#endif
    portable_desk_record r={0};uint32_t low=0,high=0;
    r.config.face=bytes[6];r.config.time_format=bytes[7];r.config.language=bytes[8];
    r.config.flip_ui=bytes[9];r.config.rtc_stores_utc=bytes[10];r.config.rtc_variant=bytes[11];
    for(unsigned i=0;i<4;++i)r.config.rtc_reference_epoch|=(uint32_t)bytes[12+i]<<(8u*i);
    for(unsigned i=0;i<4;++i){low|=(uint32_t)bytes[16+i]<<(8u*i);high|=(uint32_t)bytes[20+i]<<(8u*i);}
    uint64_t epoch=((uint64_t)high<<32)|low;
    if(epoch>INT64_MAX)return false;
    r.displayed_minute=(int64_t)epoch;r.refresh_modulo=bytes[24];r.has_image=true;
#ifdef PORTABLE_DESK_POINTS_SNAPSHOT
    memcpy(r.config.time_zone,bytes+32,40);
    if(!portable_desk_points_decode(bytes[25],bytes+80,&r.config.points))return false;
#else
    memcpy(r.config.time_zone,bytes+32,40);
#endif
    if(!portable_desk_record_valid(&r))return false;
    *out=r;return true;
}
/* Only the caller's authorized classified TIMER wake can select reuse. Any
 * config change forces a new full frame; no old frame with a different face,
 * time zone, format or orientation can be used for differential refresh. */
static inline bool portable_desk_begin(portable_desk_cycle *c,const portable_desk_config *config,
                                      const portable_desk_record *retained,bool timer_wake) {
    if(!c || !portable_desk_config_valid(config))return false;
    portable_desk_cycle next={0};next.current.config=*config;next.active=true;
    if(timer_wake && portable_desk_record_valid(retained) && portable_desk_same_config(config,&retained->config))
        next.current=*retained;
    next.full=!next.current.has_image || next.current.refresh_modulo==0;
    *c=next;return true;
}
static inline void portable_desk_cancel(portable_desk_cycle *c) {
    if(c){c->active=false;c->pending=false;}
}
/* now_seconds must come from a qualified clock, after a successful time read. */
static inline bool portable_desk_plan_frame(portable_desk_cycle *c,int64_t now_seconds,
                                           portable_desk_frame *out) {
    if(!c || !out || !c->active || c->pending || now_seconds<0 ||
       c->attempts>=PORTABLE_DESK_CLOCK_MAX_PRESENTS)return false;
    portable_desk_frame p={0};p.minute=now_seconds-portable_desk_second_in_minute(now_seconds);
    p.full=c->full;p.has_previous=c->current.has_image&&!p.full;
    p.previous_minute=p.has_previous?c->current.displayed_minute:0;
    c->planned_minute=p.minute;c->pending=true;++c->attempts;*out=p;return true;
}
/* Call only after checked present completion, never after submit acceptance.
 * A failed/unknown present cannot advance the physical-image checkpoint. */
static inline bool portable_desk_presented(portable_desk_cycle *c,bool success) {
    if(!c || !c->active || !c->pending)return false;
    c->pending=false;
    if(!success){c->active=false;return false;}
    c->current.displayed_minute=c->planned_minute;c->current.has_image=true;return true;
}
/* Read time again AFTER checked peripheral preparation. If preparation crossed
 * a minute boundary, resume peripherals and repaint, within the same 3-frame
 * bound. READY merely proposes a payload: only checked native deep entry may
 * commit it. A refusal must not publish this record as a successful sleep. */
static inline int portable_desk_prepare_record(portable_desk_cycle *c,int64_t seconds,
        int32_t microseconds,portable_desk_record *out,uint32_t *sleep_ms) {
    if(!c || !out || !sleep_ms || !c->active || c->pending || !c->attempts ||
       !c->current.has_image || seconds<0 || microseconds<0 || microseconds>=1000000){
        portable_desk_cancel(c);return PORTABLE_DESK_STOP;
    }
    if(c->current.displayed_minute!=seconds-portable_desk_second_in_minute(seconds)){
        if(c->attempts<PORTABLE_DESK_CLOCK_MAX_PRESENTS)return PORTABLE_DESK_REPAINT;
        portable_desk_cancel(c);return PORTABLE_DESK_STOP;
    }
    uint32_t us=(uint32_t)((60-portable_desk_second_in_minute(seconds))*1000000)- (uint32_t)microseconds;
    portable_desk_record proposed=c->current;
    proposed.refresh_modulo=(uint8_t)((proposed.refresh_modulo+1u)%PORTABLE_DESK_CLOCK_FULL_PERIOD);
    *out=proposed;*sleep_ms=(us+999u)/1000u;return PORTABLE_DESK_READY;
}
