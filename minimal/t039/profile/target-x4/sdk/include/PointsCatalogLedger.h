#ifndef UTILITIES_POINTS_CATALOG_LEDGER_H
#define UTILITIES_POINTS_CATALOG_LEDGER_H
#include "PointsCatalog.h"
#define POINTS_LEDGER_HEADER_BYTES 64u
#define POINTS_LEDGER_ENTRY_BYTES 16u
typedef struct { uint32_t id,revision,day; uint8_t delivered; } points_catalog_cursor;
typedef struct {
    uint32_t revision,generation,count,time_domain;
    uint32_t event_id,event_revision,parent_day,deadline,recovery_until;
    uint16_t timezone_index;
    uint8_t edge,state,mode,silenced;
    points_catalog_cursor *entries;
} points_catalog_ledger;
static inline void points_catalog_ledger_dispose(points_catalog_ledger *l) {
    if(l){POINTS_CATALOG_FREE(l->entries);memset(l,0,sizeof(*l));}
}
static inline const points_catalog_cursor *points_catalog_cursor_find(const points_catalog_ledger *l,uint32_t id) {
    if(!l)return NULL;
    uint32_t lo=0,hi=l->count;
    while(lo<hi){uint32_t m=lo+(hi-lo)/2;if(l->entries[m].id<id)lo=m+1;else hi=m;}
    return lo<l->count&&l->entries[lo].id==id?&l->entries[lo]:NULL;
}
static inline void points_catalog_ledger_clear_active(points_catalog_ledger *l) {
    l->event_id=l->event_revision=l->parent_day=l->deadline=l->recovery_until=0;
    l->edge=l->state=l->mode=l->silenced=0;l->timezone_index=0;
}
static inline bool points_catalog_ledger_size(uint32_t count,uint32_t *n) {
    uint64_t size=POINTS_LEDGER_HEADER_BYTES+UINT64_C(4)+(uint64_t)count*POINTS_LEDGER_ENTRY_BYTES;
    if(!n||size>UINT32_MAX||size>SIZE_MAX)return false;
    *n=(uint32_t)size;return true;
}
static inline bool points_catalog_ledger_valid(const points_catalog_ledger *l) {
    uint32_t n;
    if(!l||!l->revision||!l->generation||l->time_domain>1||l->timezone_index>=419||
       (!l->time_domain&&l->timezone_index)||l->state>ALARM_OCC_EXPIRED||l->silenced>1||
       (l->count&&!l->entries)||!points_catalog_ledger_size(l->count,&n))return false;
    for(uint32_t i=0;i<l->count;i++) {
        const points_catalog_cursor *e=&l->entries[i];
        if(!e->id||!e->revision||e->day>36525||(e->delivered&~7u)||(!e->day&&e->delivered)||
           (i&&l->entries[i-1].id>=e->id))return false;
    }
    if(!l->state)return !l->event_id&&!l->event_revision&&!l->parent_day&&!l->deadline&&!l->recovery_until&&
        !l->edge&&!l->mode&&!l->silenced&&!l->timezone_index;
    const points_catalog_cursor *e=points_catalog_cursor_find(l,l->event_id);
    return e&&e->revision==l->event_revision&&l->parent_day&&l->parent_day==e->day&&l->edge<3&&
        (e->delivered&(1u<<l->edge))&&l->mode>=1&&l->mode<=3&&l->deadline&&
        l->deadline<=ALARM_RTC_MAX-ALARM_RECOVERY_SECONDS&&l->recovery_until==l->deadline+ALARM_RECOVERY_SECONDS;
}
static inline int points_catalog_ledger_clone(points_catalog_ledger *out,const points_catalog_ledger *in) {
    if(!out||!in||(in->count&&!in->entries)||(uint64_t)in->count*sizeof(*in->entries)>SIZE_MAX)return POINTS_CATALOG_INVALID;
    points_catalog_ledger l=*in;l.entries=NULL;
    if(l.count){l.entries=POINTS_CATALOG_ALLOC((size_t)l.count*sizeof(*l.entries));if(!l.entries)return POINTS_CATALOG_MEMORY;
        memcpy(l.entries,in->entries,(size_t)l.count*sizeof(*l.entries));}
    points_catalog_ledger_dispose(out);*out=l;return POINTS_CATALOG_OK;
}
/* Every schedule scan owns its cursor array. A failed/uncertain write can never
 * mutate the committed ledger through a shallow copy. */
static inline int points_catalog_ledger_reconcile(points_catalog_ledger *out,const points_catalog_ledger *in,const points_catalog *c) {
    if(!out||!in||!points_catalog_valid(c)||(uint64_t)c->event_count*sizeof(points_catalog_cursor)>SIZE_MAX)return POINTS_CATALOG_INVALID;
    points_catalog_ledger l=*in;l.entries=NULL;l.count=c->event_count;l.revision=c->revision;l.time_domain=c->time_domain;
    if(l.count){l.entries=POINTS_CATALOG_ALLOC((size_t)l.count*sizeof(*l.entries));if(!l.entries)return POINTS_CATALOG_MEMORY;}
    for(uint32_t i=0;i<l.count;i++) {
        const points_catalog_item *e=&c->events[i];const points_catalog_cursor *old=points_catalog_cursor_find(in,e->id);
        l.entries[i]=old&&old->revision==e->revision?*old:(points_catalog_cursor){.id=e->id,.revision=e->revision};
    }
    const points_catalog_item *active=points_catalog_find_event(c,l.event_id);
    if(!active||!active->enabled||active->revision!=l.event_revision)points_catalog_ledger_clear_active(&l);
    points_catalog_ledger_dispose(out);*out=l;return POINTS_CATALOG_OK;
}
static inline bool points_catalog_ledger_handled(const points_catalog_ledger *l,uint32_t id,uint32_t day,unsigned edge) {
    const points_catalog_cursor *e=points_catalog_cursor_find(l,id);
    if(!e||!day||edge>=3)return true;
    return day<e->day||(day==e->day&&(e->delivered&(1u<<edge)));
}
static inline bool points_catalog_ledger_mark(points_catalog_ledger *l,uint32_t id,uint32_t day,unsigned edge) {
    const points_catalog_cursor *found=points_catalog_cursor_find(l,id);
    if(!found||!day||day>36525||edge>=3||day<found->day)return false;
    points_catalog_cursor *e=&l->entries[found-l->entries];
    if(day>e->day){e->day=day;e->delivered=0;}
    e->delivered|=(uint8_t)(1u<<edge);return true;
}
static inline int points_catalog_ledger_encode(const points_catalog_ledger *l,uint8_t *b,uint32_t cap,uint32_t *used) {
    uint32_t n;if(used)*used=0;
    if(!used||!b||!points_catalog_ledger_valid(l)||!points_catalog_ledger_size(l->count,&n)||cap<n)return POINTS_CATALOG_INVALID;
    memset(b,0,n);memcpy(b,"PTL2",4);alarm_write32(b+4,2);alarm_write32(b+8,l->revision);alarm_write32(b+12,l->generation);
    alarm_write32(b+16,l->count);alarm_write32(b+20,l->time_domain);alarm_write32(b+24,l->event_id);
    alarm_write32(b+28,l->event_revision);alarm_write32(b+32,l->parent_day);alarm_write32(b+36,l->deadline);
    alarm_write32(b+40,l->recovery_until);points_catalog_put16(b+44,l->timezone_index);
    b[46]=l->edge;b[47]=l->state;b[48]=l->mode;b[49]=l->silenced;alarm_write32(b+52,n);
    for(uint32_t i=0;i<l->count;i++){uint8_t *p=b+64+i*16;alarm_write32(p,l->entries[i].id);
        alarm_write32(p+4,l->entries[i].revision);alarm_write32(p+8,l->entries[i].day);p[12]=l->entries[i].delivered;}
    alarm_write32(b+n-4,points_catalog_hash(b,n-4));*used=n;return POINTS_CATALOG_OK;
}
static inline int points_catalog_ledger_decode(points_catalog_ledger *out,const uint8_t *b,uint32_t n) {
    uint32_t size;
    if(!out||!b||n<68||memcmp(b,"PTL2",4)||alarm_read32(b+4)!=2||alarm_read32(b+52)!=n||
       !points_catalog_zero(b+50,2)||!points_catalog_zero(b+56,8)||
       !points_catalog_ledger_size(alarm_read32(b+16),&size)||n!=size||alarm_read32(b+n-4)!=points_catalog_hash(b,n-4))return POINTS_CATALOG_INVALID;
    points_catalog_ledger l={.revision=alarm_read32(b+8),.generation=alarm_read32(b+12),.count=alarm_read32(b+16),
        .time_domain=alarm_read32(b+20),.event_id=alarm_read32(b+24),.event_revision=alarm_read32(b+28),.parent_day=alarm_read32(b+32),
        .deadline=alarm_read32(b+36),.recovery_until=alarm_read32(b+40),.timezone_index=points_catalog_u16(b+44),
        .edge=b[46],.state=b[47],.mode=b[48],.silenced=b[49]};
    if((uint64_t)l.count*sizeof(*l.entries)>SIZE_MAX)return POINTS_CATALOG_INVALID;
    if(l.count){l.entries=POINTS_CATALOG_ALLOC((size_t)l.count*sizeof(*l.entries));if(!l.entries)return POINTS_CATALOG_MEMORY;}
    for(uint32_t i=0;i<l.count;i++){const uint8_t *p=b+64+i*16;
        if(!points_catalog_zero(p+13,3)){points_catalog_ledger_dispose(&l);return POINTS_CATALOG_INVALID;}
        l.entries[i]=(points_catalog_cursor){alarm_read32(p),alarm_read32(p+4),alarm_read32(p+8),p[12]};}
    if(!points_catalog_ledger_valid(&l)){points_catalog_ledger_dispose(&l);return POINTS_CATALOG_INVALID;}
    points_catalog_ledger_dispose(out);*out=l;return POINTS_CATALOG_OK;
}
static inline bool points_catalog_legacy_matches(const points_catalog_item *e,const points_config *old) {
    if(!e||!old||e->id<1||e->id>POINTS_MAX||e->revision!=old->revision||e->created!=old->created)return false;
    const points_item *p=&old->points[e->id-1];
    return e->type_id==p->kind&&e->enabled==p->enabled&&e->mode==p->mode&&e->weekdays==p->weekdays&&
        e->hour==p->hour&&e->minute==p->minute&&e->duration_minutes==p->duration_minutes&&
        e->notify_end==p->notify_end&&e->warn3==p->warn3;
}
static inline int points_catalog_ledger_migrate(points_catalog_ledger *out,const points_catalog *c,const points_config *old,const points_ledger *legacy) {
    points_catalog_ledger empty={0},l={0};
    int rc=points_catalog_ledger_reconcile(&l,&empty,c);if(rc)return rc;
    l.generation=legacy->generation;
    if(legacy->generation&&legacy->revision==old->revision) {
        for(uint32_t i=0;i<l.count;i++)if(points_catalog_legacy_matches(&c->events[i],old)) {
            unsigned slot=l.entries[i].id-1;l.entries[i].day=legacy->day[slot];l.entries[i].delivered=legacy->delivered[slot];
        }
        const points_catalog_item *e=points_catalog_find_event(c,(uint32_t)legacy->slot+1);
        if(legacy->state&&points_catalog_legacy_matches(e,old)&&e->enabled&&legacy->day[legacy->slot]&&
           (legacy->delivered[legacy->slot]&(1u<<legacy->edge))) {
            l.event_id=e->id;l.event_revision=e->revision;l.parent_day=legacy->day[legacy->slot];l.deadline=legacy->deadline;
            l.recovery_until=legacy->recovery_until;l.edge=legacy->edge;l.state=legacy->state;l.mode=legacy->mode;l.silenced=legacy->silenced;
#ifdef ALARM_NATIVE_UTC
            l.timezone_index=legacy->timezone_index;
#endif
        }
    }
    points_catalog_ledger_dispose(out);*out=l;return POINTS_CATALOG_OK;
}
#endif
