#ifndef UTILITIES_POINTS_RECORDS_H
#define UTILITIES_POINTS_RECORDS_H
#include "AlarmRecords.h"
#define POINTS_MAX 8u
#define POINTS_RECORD_SIZE 64u
#ifdef ALARM_NATIVE_UTC
#define POINTS_CONFIG_KEY "points_utc_cfg"
#define POINTS_META_KEY "points_utc_meta"
#define POINTS_OCCURRENCE_KEY "points_utc_occ"
#else
#define POINTS_CONFIG_KEY "points_cfg"
#define POINTS_META_KEY "points_meta"
#define POINTS_OCCURRENCE_KEY "points_occ"
#endif
#define POINTS_DURATION_MAX 720u
#define POINTS_EMPTY 0u
#define POINTS_WORK_START 1u
#define POINTS_WORK_END 2u
#define POINTS_LUNCH 3u
#define POINTS_BREAK 4u
#define POINTS_BEDTIME 5u
#define POINTS_CUSTOM_1 6u
#define POINTS_CUSTOM_2 7u
#define POINTS_CUSTOM_COUNT 2u
#define POINTS_CUSTOM_NAME_MAX 13u
#define POINTS_DEFAULTS_AVAILABLE 1
#define POINTS_COLOR_COUNT 8u
#define POINTS_EDGE_START 0u
#define POINTS_EDGE_END 1u
#define POINTS_EDGE_WARNING 2u
#define POINTS_EDGE_COUNT 3u
#define POINTS_KIND_BASE 3u
typedef struct {
    uint8_t kind,enabled,mode,weekdays,hour,minute;
    uint16_t duration_minutes;
    uint8_t notify_end,warn3;
} points_item;
typedef struct { uint32_t revision,created; points_item points[POINTS_MAX]; } points_config;
typedef struct { uint8_t color; char name[POINTS_CUSTOM_NAME_MAX+1]; } points_custom_type;
typedef struct { uint32_t revision; points_custom_type custom[POINTS_CUSTOM_COUNT]; } points_meta;
typedef struct {
    uint32_t revision,generation,deadline,recovery_until;
    uint8_t slot,edge,state,mode,silenced;
    uint16_t day[POINTS_MAX];
    uint8_t delivered[POINTS_MAX];
#ifdef ALARM_NATIVE_UTC
    uint16_t timezone_index; /* Frozen 419-entry catalog; preserves pending UTC identity. */
#endif
} points_ledger;
/* Temporary factory schedule. A present record, even an empty one, always wins.
 * Revision one also makes the first user edit revision two, so service cursors
 * cannot confuse that edit with the virtual factory catalog. No startup writes. */
static inline points_config points_default_config(void) {
    return (points_config){.revision=1,.created=0,.points={
        {POINTS_CUSTOM_2,1,3,30,4,30,0,0,0},
        {POINTS_CUSTOM_1,1,3,30,5,30,15,0,0},
        {POINTS_WORK_START,1,3,30,6,0,0,0,0},
        {POINTS_BREAK,1,3,30,9,0,15,0,1},
        {POINTS_LUNCH,1,3,30,12,0,30,0,1},
        {POINTS_BREAK,1,3,30,14,15,15,0,1},
        {POINTS_WORK_END,1,3,30,16,30,0,0,0}
    }};
}
static inline points_meta points_default_meta(void) {
    return (points_meta){.revision=1,.custom={
        {.color=6,.name="Drive to Work"},{.color=0,.name="Wakeup"}
    }};
}
static inline uint32_t points_checksum(const uint8_t *p) {
    uint32_t h=2166136261u;for(unsigned i=0;i<60;i++)h=(h^p[i])*16777619u;return h;
}
static inline bool points_duration_kind(unsigned kind) {
    return kind==POINTS_LUNCH||kind==POINTS_BREAK||kind==POINTS_CUSTOM_1||kind==POINTS_CUSTOM_2;
}
static inline bool points_config_valid(const points_config *c) {
    if(!c||!c->revision||c->created>ALARM_RTC_MAX-ALARM_RECOVERY_SECONDS)return false;
    for(unsigned i=0;i<POINTS_MAX;i++) {
        const points_item *p=&c->points[i];
        if(p->kind==POINTS_EMPTY) {
            if(p->enabled||p->mode||p->weekdays||p->hour||p->minute||p->duration_minutes||p->notify_end||p->warn3)return false;
            continue;
        }
        if(p->kind<POINTS_WORK_START||p->kind>POINTS_CUSTOM_2||p->enabled>1||p->mode>3||
           p->weekdays>127||(p->enabled&&!p->weekdays)||p->hour>23||p->minute>59||
           p->duration_minutes>POINTS_DURATION_MAX||p->notify_end>1||p->warn3>1||
           (p->duration_minutes&&!points_duration_kind(p->kind))||
           (p->notify_end&&!p->duration_minutes)||(p->warn3&&p->duration_minutes<3))return false;
    }return true;
}
static inline void points_config_encode(const points_config *c,uint8_t b[POINTS_RECORD_SIZE]) {
    memset(b,0,POINTS_RECORD_SIZE);memcpy(b,"PTC1",4);alarm_write32(b+4,c->revision);alarm_write32(b+8,c->created);
    for(unsigned i=0;i<POINTS_MAX;i++) {
        const points_item *p=&c->points[i];uint8_t *q=b+12+i*6;
        q[0]=(uint8_t)(p->kind|(p->mode<<3)|(p->enabled<<5)|(p->notify_end<<6)|(p->warn3<<7));
        q[1]=p->weekdays;q[2]=p->hour;q[3]=p->minute;q[4]=(uint8_t)p->duration_minutes;q[5]=(uint8_t)(p->duration_minutes>>8);
    }alarm_write32(b+60,points_checksum(b));
}
static inline bool points_config_decode(points_config *c,const uint8_t *b,uint32_t n) {
    if(!c||!b||n!=POINTS_RECORD_SIZE||memcmp(b,"PTC1",4)||alarm_read32(b+60)!=points_checksum(b))return false;
    points_config v={.revision=alarm_read32(b+4),.created=alarm_read32(b+8)};
    for(unsigned i=0;i<POINTS_MAX;i++) {
        const uint8_t *q=b+12+i*6;
        v.points[i]=(points_item){(uint8_t)(q[0]&7),(uint8_t)((q[0]>>5)&1),(uint8_t)((q[0]>>3)&3),q[1],q[2],q[3],
            (uint16_t)(q[4]|((uint16_t)q[5]<<8)),(uint8_t)((q[0]>>6)&1),(uint8_t)((q[0]>>7)&1)};
    }if(!points_config_valid(&v))return false;*c=v;return true;
}
static inline bool points_custom_name_valid(const char *name) {
    if(!name)return false;
    unsigned n=0;
    while(n<POINTS_CUSTOM_NAME_MAX&&name[n]){unsigned c=(unsigned char)name[n];if(c<32||c>126)return false;n++;}
    return !name[n];
}
static inline bool points_meta_valid(const points_meta *m) {
    if(!m)return false;
    for(unsigned i=0;i<POINTS_CUSTOM_COUNT;i++) {
        const points_custom_type *t=&m->custom[i];
        if(t->color>=POINTS_COLOR_COUNT||!points_custom_name_valid(t->name))return false;
        if(!t->name[0]&&t->color)return false;
    }return true;
}
static inline void points_meta_encode(const points_meta *m,uint8_t b[POINTS_RECORD_SIZE]) {
    unsigned stride=(strlen(m->custom[0].name)>12||strlen(m->custom[1].name)>12)?15u:14u;
    memset(b,0,POINTS_RECORD_SIZE);memcpy(b,stride==15?"PTM2":"PTM1",4);alarm_write32(b+4,m->revision);
    for(unsigned i=0;i<POINTS_CUSTOM_COUNT;i++) {
        const points_custom_type *t=&m->custom[i];uint8_t *q=b+8+i*stride;unsigned n=0;
        while(n<POINTS_CUSTOM_NAME_MAX&&t->name[n])n++;
        q[0]=t->color;q[1]=(uint8_t)n;if(n)memcpy(q+2,t->name,n);
    }alarm_write32(b+60,points_checksum(b));
}
static inline bool points_meta_decode(points_meta *m,const uint8_t *b,uint32_t n) {
    if(!m||!b||n!=POINTS_RECORD_SIZE||alarm_read32(b+60)!=points_checksum(b))return false;
    unsigned stride=!memcmp(b,"PTM1",4)?14u:!memcmp(b,"PTM2",4)?15u:0u;
    if(!stride)return false;
    for(unsigned i=8+2*stride;i<60;i++)if(b[i])return false;
    points_meta v={.revision=alarm_read32(b+4)};
    for(unsigned i=0;i<POINTS_CUSTOM_COUNT;i++) {
        const uint8_t *q=b+8+i*stride;if(q[0]>=POINTS_COLOR_COUNT||q[1]>stride-2)return false;
        v.custom[i].color=q[0];if(q[1])memcpy(v.custom[i].name,q+2,q[1]);v.custom[i].name[q[1]]=0;
        for(unsigned j=q[1];j<stride-2;j++)if(q[2+j])return false;
    }if(!points_meta_valid(&v))return false;*m=v;return true;
}
static inline bool points_ledger_valid(const points_ledger *l) {
    if(!l||
#ifdef ALARM_NATIVE_UTC
       l->timezone_index>=419u||
#endif
       !l->revision||!l->generation||l->slot>=POINTS_MAX||l->edge>=POINTS_EDGE_COUNT||l->state>ALARM_OCC_EXPIRED||l->silenced>1)return false;
    for(unsigned i=0;i<POINTS_MAX;i++)if(l->day[i]>36525||(l->delivered[i]&~7u)||(!l->day[i]&&l->delivered[i]))return false;
    if(!l->state)return !l->slot&&!l->edge&&!l->deadline&&!l->recovery_until&&!l->mode&&!l->silenced;
    return l->mode>=1&&l->mode<=3&&l->deadline&&l->deadline<=ALARM_RTC_MAX-ALARM_RECOVERY_SECONDS&&l->recovery_until==l->deadline+ALARM_RECOVERY_SECONDS;
}
static inline void points_ledger_encode(const points_ledger *l,uint8_t b[POINTS_RECORD_SIZE]) {
    memset(b,0,POINTS_RECORD_SIZE);memcpy(b,l->silenced?"PTO3":"PTO2",4);alarm_write32(b+4,l->revision);alarm_write32(b+8,l->generation);
    alarm_write32(b+12,l->deadline);alarm_write32(b+16,l->recovery_until);
    b[20]=l->slot;b[21]=l->edge;b[22]=l->state;b[23]=l->mode;
    b[48]=l->silenced;
#ifdef ALARM_NATIVE_UTC
    memcpy(b,"PTU1",4);b[50]=(uint8_t)l->timezone_index;b[51]=(uint8_t)(l->timezone_index>>8);
#endif
    for(unsigned i=0;i<POINTS_MAX;i++){b[24+i*2]=(uint8_t)l->day[i];b[25+i*2]=(uint8_t)(l->day[i]>>8);b[40+i]=l->delivered[i];}
    alarm_write32(b+60,points_checksum(b));
}
static inline bool points_ledger_decode(points_ledger *l,const uint8_t *b,uint32_t n) {
    if(!l||!b||n!=POINTS_RECORD_SIZE||alarm_read32(b+60)!=points_checksum(b))return false;
    points_ledger v={0};
    #ifdef ALARM_NATIVE_UTC
    if(!memcmp(b,"PTU1",4)) {
        if(b[48]>1||b[49])return false;
        for(unsigned i=52;i<60;i++)if(b[i])return false;
        v=(points_ledger){.revision=alarm_read32(b+4),.generation=alarm_read32(b+8),.deadline=alarm_read32(b+12),
            .recovery_until=alarm_read32(b+16),.slot=b[20],.edge=b[21],.state=b[22],.mode=b[23],.silenced=b[48],
            .timezone_index=(uint16_t)(b[50]|((uint16_t)b[51]<<8))};
        for(unsigned i=0;i<POINTS_MAX;i++){v.day[i]=(uint16_t)(b[24+i*2]|((uint16_t)b[25+i*2]<<8));v.delivered[i]=b[40+i];}
    }
#else
    if(!memcmp(b,"PTO2",4)||!memcmp(b,"PTO3",4)) {
        bool muted=!memcmp(b,"PTO3",4);if(b[48]!=(muted?1:0))return false;
        for(unsigned i=49;i<60;i++)if(b[i])return false;
        v=(points_ledger){.revision=alarm_read32(b+4),.generation=alarm_read32(b+8),.deadline=alarm_read32(b+12),
            .recovery_until=alarm_read32(b+16),.slot=b[20],.edge=b[21],.state=b[22],.mode=b[23],.silenced=b[48]};
        for(unsigned i=0;i<POINTS_MAX;i++){v.day[i]=(uint16_t)(b[24+i*2]|((uint16_t)b[25+i*2]<<8));v.delivered[i]=b[40+i];}
    } else if(!memcmp(b,"PTO1",4)) {
        if(alarm_read32(b+56))return false;
        v=(points_ledger){.revision=alarm_read32(b+4),.generation=alarm_read32(b+8),.deadline=alarm_read32(b+12),
            .recovery_until=alarm_read32(b+16),.slot=b[20],.edge=b[21],.state=b[22],.mode=b[23]};
        if(v.edge>POINTS_EDGE_END)return false;
        for(unsigned i=0;i<POINTS_MAX;i++) {
            uint16_t s=(uint16_t)(b[24+i*4]|((uint16_t)b[25+i*4]<<8));
            uint16_t e=(uint16_t)(b[26+i*4]|((uint16_t)b[27+i*4]<<8));
            v.day[i]=s>e?s:e;
            if(v.day[i]){if(s==v.day[i])v.delivered[i]|=1u<<POINTS_EDGE_START;if(e==v.day[i])v.delivered[i]|=1u<<POINTS_EDGE_END;}
        }
    }
#endif
    else return false;
    if(!points_ledger_valid(&v))return false;
    *l=v;return true;
}
static inline bool points_ledger_handled(const points_ledger *l,unsigned slot,uint32_t parent_day,unsigned edge) {
    if(!l||slot>=POINTS_MAX||edge>=POINTS_EDGE_COUNT||!parent_day)return true;
    return parent_day<l->day[slot]||(parent_day==l->day[slot]&&(l->delivered[slot]&(1u<<edge)));
}
static inline bool points_ledger_mark(points_ledger *l,unsigned slot,uint32_t parent_day,unsigned edge) {
    if(!l||slot>=POINTS_MAX||edge>=POINTS_EDGE_COUNT||!parent_day||parent_day>36525||parent_day<l->day[slot])return false;
    if(parent_day>l->day[slot]){l->day[slot]=(uint16_t)parent_day;l->delivered[slot]=0;}
    l->delivered[slot]|=(uint8_t)(1u<<edge);return true;
}
static inline const char *points_label(unsigned kind,unsigned edge) {
    switch(kind){case POINTS_WORK_START:return edge?"WORK ENDED":"WORK START";case POINTS_WORK_END:return edge?"WORK END DONE":"WORK END";
    case POINTS_LUNCH:return edge?"LUNCH ENDED":"LUNCH";case POINTS_BREAK:return edge?"BREAK ENDED":"BREAK";
    case POINTS_BEDTIME:return edge?"WIND DOWN END":"BEDTIME";case POINTS_CUSTOM_1:return "CUSTOM 1";case POINTS_CUSTOM_2:return "CUSTOM 2";
    default:return "POINTS IN TIME";}
}
static inline uint32_t points_token_kind(unsigned slot,unsigned edge){return POINTS_KIND_BASE+slot*POINTS_EDGE_COUNT+edge;}
#endif
