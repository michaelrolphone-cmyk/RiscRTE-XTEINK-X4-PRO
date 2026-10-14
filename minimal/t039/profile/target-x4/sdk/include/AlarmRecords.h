#ifndef UTILITIES_ALARM_RECORDS_H
#define UTILITIES_ALARM_RECORDS_H
#include "AlarmServiceV1.h"
#include <stddef.h>
#include <string.h>
#define ALARM_RECORD_SIZE 32u
#ifdef ALARM_NATIVE_UTC
/* UTC seconds since 2000; native signed Unix seconds stop in January 2038. */
#define ALARM_RTC_MAX (2147483647u-946684800u)
#else
#define ALARM_RTC_MAX 3155759999u
#endif
#define ALARM_COUNTDOWN_MAX 359999u /* 99:59:59 */
#define ALARM_RECOVERY_SECONDS 60u
#define ALARM_INVOCATION_MS 20000u
#ifdef ALARM_NATIVE_UTC
#define ALARM_CONFIG_KEY "alarm_utc_cfg"
#define ALARM_TIMER_KEY "timer_utc_cfg"
#define ALARM_OCCURRENCE_KEY "alarm_utc_occ"
#define ALARM_TIMER_OCCURRENCE_KEY "timer_utc_occ"
#else
#define ALARM_CONFIG_KEY "alarm_cfg"
#define ALARM_TIMER_KEY "timer_cfg"
#define ALARM_OCCURRENCE_KEY "alarm_occ"
#define ALARM_TIMER_OCCURRENCE_KEY "timer_occ"
#endif
#define ALARM_MODE_KEY "alert_mode"
enum { ALARM_OCC_NONE, ALARM_OCC_PENDING, ALARM_OCC_ACKED, ALARM_OCC_EXPIRED };
typedef struct { uint32_t revision, deadline, created, duration; uint8_t kind, enabled; } alarm_config;
typedef struct { uint32_t revision, deadline, generation, recovery_until; uint8_t kind, state, mode, silenced; } alarm_occurrence;
static inline uint32_t alarm_read32(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static inline void alarm_write32(uint8_t *p,uint32_t n) { for(unsigned i=0;i<4;i++){p[i]=(uint8_t)n;n>>=8;} }
static inline uint32_t alarm_checksum(const uint8_t *p) {
    uint32_t h=2166136261u;for(unsigned i=0;i<28;i++)h=(h^p[i])*16777619u;return h;
}
static inline bool alarm_config_valid(const alarm_config *r) {
    return r && r->kind>=1 && r->kind<=2 && r->enabled<=1 && r->revision &&
        r->created<=ALARM_RTC_MAX && r->deadline<=ALARM_RTC_MAX-ALARM_RECOVERY_SECONDS &&
        ((!r->enabled&&!r->deadline&&!r->duration) || (r->enabled && r->deadline>r->created &&
        (r->kind==ALARM_KIND_ALARM ? r->duration==0 : r->duration && r->duration<=ALARM_COUNTDOWN_MAX && r->deadline-r->created==r->duration)));
}
static inline void alarm_config_encode(const alarm_config *r,uint8_t b[ALARM_RECORD_SIZE]) {
    memset(b,0,ALARM_RECORD_SIZE);memcpy(b,"SAC1",4);b[4]=r->kind;b[5]=r->enabled;
    alarm_write32(b+8,r->revision);alarm_write32(b+12,r->deadline);alarm_write32(b+16,r->created);
    alarm_write32(b+20,r->duration);alarm_write32(b+28,alarm_checksum(b));
}
static inline bool alarm_config_decode(alarm_config *r,const uint8_t *b,uint32_t n,uint8_t kind) {
    if(!r||!b||n!=ALARM_RECORD_SIZE||memcmp(b,"SAC1",4)||b[4]!=kind||b[6]||b[7]||alarm_read32(b+24)||alarm_read32(b+28)!=alarm_checksum(b))return false;
    alarm_config v={alarm_read32(b+8),alarm_read32(b+12),alarm_read32(b+16),alarm_read32(b+20),b[4],b[5]};
    if(!alarm_config_valid(&v))return false;
    *r=v;return true;
}
static inline bool alarm_occurrence_valid(const alarm_occurrence *r) {
    return r&&r->kind>=1&&r->kind<=2&&r->state>=ALARM_OCC_PENDING&&r->state<=ALARM_OCC_EXPIRED&&
        r->mode>=1&&r->mode<=3&&r->silenced<=1&&r->revision&&r->generation&&r->deadline&&r->deadline<=ALARM_RTC_MAX-ALARM_RECOVERY_SECONDS&&
        r->recovery_until==r->deadline+ALARM_RECOVERY_SECONDS;
}
static inline void alarm_occurrence_encode(const alarm_occurrence *r,uint8_t b[ALARM_RECORD_SIZE]) {
    memset(b,0,ALARM_RECORD_SIZE);memcpy(b,r->silenced?"SAO2":"SAO1",4);b[4]=r->kind;b[5]=r->state;b[6]=r->mode;b[7]=r->silenced;
    alarm_write32(b+8,r->revision);alarm_write32(b+12,r->deadline);alarm_write32(b+16,r->generation);
    alarm_write32(b+20,r->recovery_until);alarm_write32(b+28,alarm_checksum(b));
}
static inline bool alarm_occurrence_decode(alarm_occurrence *r,const uint8_t *b,uint32_t n,uint8_t kind) {
    if(!r||!b||n!=ALARM_RECORD_SIZE||b[4]!=kind||alarm_read32(b+24)||alarm_read32(b+28)!=alarm_checksum(b))return false;
    if(!memcmp(b,"SAO1",4)?b[7]!=0:memcmp(b,"SAO2",4)||b[7]!=1)return false;
    alarm_occurrence v={alarm_read32(b+8),alarm_read32(b+12),alarm_read32(b+16),alarm_read32(b+20),b[4],b[5],b[6],b[7]};
    if(!alarm_occurrence_valid(&v))return false;
    *r=v;return true;
}
static inline bool alarm_calendar_seconds(uint16_t y,uint8_t m,uint8_t d,uint8_t h,uint8_t min,uint8_t s,uint32_t *out) {
    static const uint8_t days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    if(!out||y<2000||y>2099||m<1||m>12||d<1||d>days[m-1]+(m==2&&y%4==0)||h>23||min>59||s>59)return false;
    uint32_t total=(uint32_t)(y-2000)*365u+(y-2000+3u)/4u;
    for(unsigned i=1;i<m;i++)total+=days[i-1]+(i==2&&y%4==0);
    *out=((total+d-1)*24u+h)*3600u+(uint32_t)min*60u+s;return true;
}
static inline bool alarm_same_occurrence(const alarm_occurrence *o,const alarm_config *c) {
    return o->state&&o->kind==c->kind&&o->revision==c->revision&&o->deadline==c->deadline;
}
static inline bool alarm_token_equal(const alarm_token_v1 *a,const alarm_token_v1 *b) {
    return a&&b&&a->kind==b->kind&&a->revision==b->revision&&a->deadline==b->deadline&&a->generation==b->generation;
}
#endif
