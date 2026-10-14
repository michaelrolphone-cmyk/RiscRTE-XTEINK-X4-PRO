#ifndef UTILITIES_POINTS_CATALOG_H
#define UTILITIES_POINTS_CATALOG_H
/* Variable-length application data, shared by the editor, scheduler and face
 * projection. Capacity belongs to the selected storage backend, not this file
 * format. IDs remain stable when entries are sorted, deleted or inserted. */
#include "PointsRecords.h"
#include <stdlib.h>
#include <limits.h>

#define POINTS_CATALOG_FILE "points.catalog"
#define POINTS_LEDGER_FILE "points.ledger"
#define POINTS_CATALOG_NAME_MAX 31u
#define POINTS_CATALOG_SCHEMA 2u
#define POINTS_CATALOG_HEADER_BYTES 44u
#define POINTS_CATALOG_EVENT_BYTES 32u
#define POINTS_CATALOG_TYPE_BYTES 64u
#define POINTS_TYPE_DURATION 1u
#define POINTS_TYPE_NOTIFY_END 2u
#define POINTS_TYPE_WARN3 4u
#define POINTS_TIME_RAW_RTC 0u
#define POINTS_TIME_NATIVE_UTC 1u
enum { POINTS_CATALOG_OK=0, POINTS_CATALOG_INVALID=-1,
       POINTS_CATALOG_MEMORY=-2, POINTS_CATALOG_EXHAUSTED=-3,
       POINTS_CATALOG_IN_USE=-4, POINTS_CATALOG_NOT_FOUND=-5 };

typedef struct {
    uint32_t id, type_id, revision, created;
    uint16_t duration_minutes;
    uint8_t mode, weekdays, hour, minute, enabled, notify_end, warn3;
} points_catalog_item;
typedef struct {
    uint32_t id, revision, color;
    char name[POINTS_CATALOG_NAME_MAX+1];
    uint16_t duration_minutes;
    uint8_t mode, flags, symbol;
} points_catalog_type;
typedef struct {
    uint32_t revision, next_event_id, next_type_id, event_count, type_count, time_domain;
    points_catalog_item *events;
    points_catalog_type *types;
} points_catalog;

#ifndef POINTS_CATALOG_ALLOC
#define POINTS_CATALOG_ALLOC malloc
#define POINTS_CATALOG_FREE free
#endif
static inline void points_catalog_dispose(points_catalog *c) {
    if(!c)return;
    POINTS_CATALOG_FREE(c->events);POINTS_CATALOG_FREE(c->types);
    memset(c,0,sizeof(*c));
}
static inline uint16_t points_catalog_u16(const uint8_t *p) {
    return (uint16_t)(p[0]|((uint16_t)p[1]<<8));
}
static inline void points_catalog_put16(uint8_t *p,uint16_t v) {
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);
}
static inline bool points_catalog_zero(const uint8_t *p,size_t n) {
    while(n--)if(*p++)return false;
    return true;
}
static inline uint32_t points_catalog_hash(const uint8_t *p,size_t n) {
    uint32_t h=UINT32_C(2166136261);
    while(n--)h=(h^*p++)*UINT32_C(16777619);
    return h;
}
static inline bool points_catalog_size(uint32_t events,uint32_t types,uint32_t *bytes) {
    uint64_t n=POINTS_CATALOG_HEADER_BYTES+UINT64_C(4)+
        (uint64_t)events*POINTS_CATALOG_EVENT_BYTES+(uint64_t)types*POINTS_CATALOG_TYPE_BYTES;
    if(!bytes||n>UINT32_MAX||n>SIZE_MAX)return false;
    *bytes=(uint32_t)n;return true;
}
static inline const points_catalog_type *points_catalog_find_type(const points_catalog *c,uint32_t id) {
    if(!c)return NULL;
    uint32_t lo=0,hi=c->type_count;
    while(lo<hi){uint32_t mid=lo+(hi-lo)/2;if(c->types[mid].id<id)lo=mid+1;else hi=mid;}
    if(lo<c->type_count&&c->types[lo].id==id)return &c->types[lo];
    return NULL;
}
static inline const points_catalog_item *points_catalog_find_event(const points_catalog *c,uint32_t id) {
    if(!c)return NULL;
    uint32_t lo=0,hi=c->event_count;
    while(lo<hi){uint32_t mid=lo+(hi-lo)/2;if(c->events[mid].id<id)lo=mid+1;else hi=mid;}
    if(lo<c->event_count&&c->events[lo].id==id)return &c->events[lo];
    return NULL;
}
static inline bool points_catalog_type_valid(const points_catalog_type *t) {
    if(!t||!t->id||!t->revision||t->color>0xffffffu||t->mode>ALARM_MODE_BOTH||
       (t->flags&~7u)||t->symbol>7||t->duration_minutes>720||!t->name[0])return false;
    unsigned n=0;while(n<=POINTS_CATALOG_NAME_MAX&&t->name[n]) {
        if((unsigned char)t->name[n]<32||(unsigned char)t->name[n]>126)return false;
        ++n;
    }
    if(!n||n>POINTS_CATALOG_NAME_MAX)return false;
    if(!(t->flags&POINTS_TYPE_DURATION)&&(t->duration_minutes||(t->flags&6u)))return false;
    if((t->flags&POINTS_TYPE_NOTIFY_END)&&!t->duration_minutes)return false;
    if((t->flags&POINTS_TYPE_WARN3)&&t->duration_minutes<3)return false;
    return true;
}
static inline bool points_catalog_item_valid(const points_catalog *c,const points_catalog_item *e) {
    if(!e||!e->id||!e->revision||e->created>ALARM_RTC_MAX||e->mode>ALARM_MODE_BOTH||
       e->weekdays>127||e->hour>23||e->minute>59||e->enabled>1||e->notify_end>1||e->warn3>1||
       e->duration_minutes>720)return false;
    const points_catalog_type *t=points_catalog_find_type(c,e->type_id);
    if(!t)return false;
    if(!(t->flags&POINTS_TYPE_DURATION)&&(e->duration_minutes||e->notify_end||e->warn3))return false;
    if(e->notify_end&&!e->duration_minutes)return false;
    if(e->warn3&&e->duration_minutes<3)return false;
    return !e->enabled||e->weekdays;
}
static inline bool points_catalog_valid(const points_catalog *c) {
    uint32_t size;
    if(!c||!c->revision||!c->next_event_id||!c->next_type_id||c->time_domain>POINTS_TIME_NATIVE_UTC||
       (c->event_count&&!c->events)||(c->type_count&&!c->types)||
       !points_catalog_size(c->event_count,c->type_count,&size))return false;
    for(uint32_t i=0;i<c->type_count;i++) {
        if(!points_catalog_type_valid(&c->types[i])||c->types[i].id>=c->next_type_id)return false;
        if(i&&c->types[i-1].id>=c->types[i].id)return false;
    }
    for(uint32_t i=0;i<c->event_count;i++) {
        if(!points_catalog_item_valid(c,&c->events[i])||c->events[i].id>=c->next_event_id)return false;
        if(i&&c->events[i-1].id>=c->events[i].id)return false;
    }
    return true;
}
static inline int points_catalog_encode(const points_catalog *c,uint8_t *bytes,uint32_t capacity,uint32_t *used) {
    if(used)*used=0;
    uint32_t n;
    if(!used||!points_catalog_valid(c)||!points_catalog_size(c->event_count,c->type_count,&n)||!bytes||capacity<n)
        return POINTS_CATALOG_INVALID;
    memset(bytes,0,n);memcpy(bytes,"PTC2",4);
    alarm_write32(bytes+4,POINTS_CATALOG_SCHEMA);alarm_write32(bytes+8,c->revision);
    alarm_write32(bytes+12,c->next_event_id);alarm_write32(bytes+16,c->next_type_id);
    alarm_write32(bytes+20,c->event_count);alarm_write32(bytes+24,c->type_count);
    alarm_write32(bytes+28,c->time_domain);alarm_write32(bytes+32,n);
    uint8_t *p=bytes+POINTS_CATALOG_HEADER_BYTES;
    for(uint32_t i=0;i<c->event_count;i++,p+=POINTS_CATALOG_EVENT_BYTES) {
        const points_catalog_item *e=&c->events[i];
        alarm_write32(p,e->id);alarm_write32(p+4,e->type_id);alarm_write32(p+8,e->revision);alarm_write32(p+12,e->created);
        points_catalog_put16(p+16,e->duration_minutes);p[18]=e->mode;p[19]=e->weekdays;p[20]=e->hour;p[21]=e->minute;
        p[22]=e->enabled;p[23]=e->notify_end;p[24]=e->warn3;
    }
    for(uint32_t i=0;i<c->type_count;i++,p+=POINTS_CATALOG_TYPE_BYTES) {
        const points_catalog_type *t=&c->types[i];
        alarm_write32(p,t->id);alarm_write32(p+4,t->revision);alarm_write32(p+8,t->color);
        memcpy(p+12,t->name,strlen(t->name));points_catalog_put16(p+44,t->duration_minutes);p[46]=t->mode;p[47]=t->flags;p[48]=t->symbol;
    }
    alarm_write32(bytes+n-4,points_catalog_hash(bytes,n-4));*used=n;return POINTS_CATALOG_OK;
}
/* Destination is untouched on malformed input or allocation failure. */
static inline int points_catalog_decode(points_catalog *out,const uint8_t *bytes,uint32_t n) {
    uint32_t expected;
    if(!out||!bytes||n<POINTS_CATALOG_HEADER_BYTES+4||memcmp(bytes,"PTC2",4)||alarm_read32(bytes+4)!=POINTS_CATALOG_SCHEMA||
       alarm_read32(bytes+32)!=n||!points_catalog_zero(bytes+36,8)||
       !points_catalog_size(alarm_read32(bytes+20),alarm_read32(bytes+24),&expected)||expected!=n||
       alarm_read32(bytes+n-4)!=points_catalog_hash(bytes,n-4))return POINTS_CATALOG_INVALID;
    points_catalog c={.revision=alarm_read32(bytes+8),.next_event_id=alarm_read32(bytes+12),
        .next_type_id=alarm_read32(bytes+16),.event_count=alarm_read32(bytes+20),.type_count=alarm_read32(bytes+24),
        .time_domain=alarm_read32(bytes+28)};
    if(c.event_count) {
        if((uint64_t)c.event_count*sizeof(*c.events)>SIZE_MAX)return POINTS_CATALOG_INVALID;
        c.events=POINTS_CATALOG_ALLOC((size_t)c.event_count*sizeof(*c.events));
        if(!c.events)return POINTS_CATALOG_MEMORY;
        memset(c.events,0,(size_t)c.event_count*sizeof(*c.events));
    }
    if(c.type_count) {
        if((uint64_t)c.type_count*sizeof(*c.types)>SIZE_MAX){points_catalog_dispose(&c);return POINTS_CATALOG_INVALID;}
        c.types=POINTS_CATALOG_ALLOC((size_t)c.type_count*sizeof(*c.types));
        if(!c.types){points_catalog_dispose(&c);return POINTS_CATALOG_MEMORY;}
        memset(c.types,0,(size_t)c.type_count*sizeof(*c.types));
    }
    const uint8_t *p=bytes+POINTS_CATALOG_HEADER_BYTES;
    for(uint32_t i=0;i<c.event_count;i++,p+=POINTS_CATALOG_EVENT_BYTES) {
        if(!points_catalog_zero(p+25,7)){points_catalog_dispose(&c);return POINTS_CATALOG_INVALID;}
        c.events[i]=(points_catalog_item){.id=alarm_read32(p),.type_id=alarm_read32(p+4),.revision=alarm_read32(p+8),
            .created=alarm_read32(p+12),.duration_minutes=points_catalog_u16(p+16),.mode=p[18],.weekdays=p[19],
            .hour=p[20],.minute=p[21],.enabled=p[22],.notify_end=p[23],.warn3=p[24]};
    }
    for(uint32_t i=0;i<c.type_count;i++,p+=POINTS_CATALOG_TYPE_BYTES) {
        if(!points_catalog_zero(p+49,15)){points_catalog_dispose(&c);return POINTS_CATALOG_INVALID;}
        points_catalog_type *t=&c.types[i];t->id=alarm_read32(p);t->revision=alarm_read32(p+4);t->color=alarm_read32(p+8);
        memcpy(t->name,p+12,sizeof(t->name));t->duration_minutes=points_catalog_u16(p+44);t->mode=p[46];t->flags=p[47];t->symbol=p[48];
        size_t len=0;while(len<sizeof(t->name)&&t->name[len])++len;
        if(len==sizeof(t->name)||!points_catalog_zero(p+12+len,sizeof(t->name)-len)){
            points_catalog_dispose(&c);return POINTS_CATALOG_INVALID;
        }
    }
    if(!points_catalog_valid(&c)){points_catalog_dispose(&c);return POINTS_CATALOG_INVALID;}
    points_catalog_dispose(out);*out=c;return POINTS_CATALOG_OK;
}
static inline int points_catalog_clone(points_catalog *out,const points_catalog *source) {
    if(!out||!points_catalog_valid(source))return POINTS_CATALOG_INVALID;
    points_catalog c=*source;c.events=NULL;c.types=NULL;
    if(c.event_count){c.events=POINTS_CATALOG_ALLOC((size_t)c.event_count*sizeof(*c.events));if(!c.events)return POINTS_CATALOG_MEMORY;
        memcpy(c.events,source->events,(size_t)c.event_count*sizeof(*c.events));}
    if(c.type_count){c.types=POINTS_CATALOG_ALLOC((size_t)c.type_count*sizeof(*c.types));if(!c.types){points_catalog_dispose(&c);return POINTS_CATALOG_MEMORY;}
        memcpy(c.types,source->types,(size_t)c.type_count*sizeof(*c.types));}
    points_catalog_dispose(out);*out=c;return POINTS_CATALOG_OK;
}
/* Legacy entries keep their slot-derived stable ID and original creation and
 * revision boundary. The occurrence migration can therefore match all eight
 * old slots, including holes, without moving an event onto another ledger. */
static inline int points_catalog_migrate(points_catalog *out,const points_config *old,const points_meta *meta,uint32_t domain) {
    if(!out||!points_config_valid(old)||!points_meta_valid(meta)||domain>POINTS_TIME_NATIVE_UTC)return POINTS_CATALOG_INVALID;
    static const char *const names[]={"Work","Work End","Lunch","Break","Bedtime"};
    static const uint32_t colors[]={0x3d9bffu,0xff3d71u,0xffb020u,0x3dff9au,0x6d7bffu};
    static const uint8_t symbols[]={1,5,3,2,7};
    static const uint32_t custom_colors[]={0xffd24au,0xff7a1au,0xff3d71u,0xb24dffu,0x6d7bffu,0x3d9bffu,0x19e3ffu,0x3dff9au};
    points_catalog c={.revision=old->revision,.next_event_id=POINTS_MAX+1,.next_type_id=8,.type_count=7,.time_domain=domain};
    for(unsigned i=0;i<POINTS_MAX;i++)if(old->points[i].kind)++c.event_count;
    c.types=POINTS_CATALOG_ALLOC(c.type_count*sizeof(*c.types));if(!c.types)return POINTS_CATALOG_MEMORY;
    memset(c.types,0,c.type_count*sizeof(*c.types));
    for(unsigned i=0;i<5;i++) {
        c.types[i]=(points_catalog_type){.id=i+1,.revision=1,.color=colors[i],.symbol=symbols[i],.flags=(i==2||i==3)?POINTS_TYPE_DURATION:0};
        memcpy(c.types[i].name,names[i],strlen(names[i])+1);
    }
    for(unsigned i=0;i<POINTS_CUSTOM_COUNT;i++) {
        const points_custom_type *m=&meta->custom[i];
        c.types[5+i]=(points_catalog_type){.id=6+i,.revision=meta->revision?meta->revision:1,
            .color=custom_colors[m->color%POINTS_COLOR_COUNT],.symbol=m->color%POINTS_COLOR_COUNT,.flags=POINTS_TYPE_DURATION};
        if(m->name[0])memcpy(c.types[5+i].name,m->name,sizeof(m->name));
        else memcpy(c.types[5+i].name,i?"Custom 2":"Custom 1",9);
    }
    if(c.event_count){c.events=POINTS_CATALOG_ALLOC(c.event_count*sizeof(*c.events));if(!c.events){points_catalog_dispose(&c);return POINTS_CATALOG_MEMORY;}}
    uint32_t at=0;
    for(unsigned i=0;i<POINTS_MAX;i++)if(old->points[i].kind) {
        const points_item *p=&old->points[i];
        c.events[at++]=(points_catalog_item){.id=i+1,.type_id=p->kind,.revision=old->revision,.created=old->created,
            .duration_minutes=p->duration_minutes,.mode=p->mode,.weekdays=p->weekdays,.hour=p->hour,.minute=p->minute,
            .enabled=p->enabled,.notify_end=p->notify_end,.warn3=p->warn3};
    }
    if(!points_catalog_valid(&c)){points_catalog_dispose(&c);return POINTS_CATALOG_INVALID;}
    points_catalog_dispose(out);*out=c;return POINTS_CATALOG_OK;
}

/* Mutations change a private draft only. The caller atomically replaces the
 * complete catalog with its expected backend revision before publishing it. */
static inline int points_catalog_add_event(points_catalog *c,const points_catalog_item *draft,uint32_t *id) {
    if(id)*id=0;
    if(!id||!points_catalog_valid(c)||!draft)return POINTS_CATALOG_INVALID;
    if(c->revision==UINT32_MAX||c->next_event_id==UINT32_MAX||c->event_count==UINT32_MAX)return POINTS_CATALOG_EXHAUSTED;
    points_catalog_item e=*draft;e.id=c->next_event_id;e.revision=1;
    if(!points_catalog_item_valid(c,&e))return POINTS_CATALOG_INVALID;
    uint32_t bytes;
    if(!points_catalog_size(c->event_count+1,c->type_count,&bytes)||(uint64_t)(c->event_count+1)*sizeof(e)>SIZE_MAX)
        return POINTS_CATALOG_EXHAUSTED;
    points_catalog_item *next=POINTS_CATALOG_ALLOC((size_t)(c->event_count+1)*sizeof(e));
    if(!next)return POINTS_CATALOG_MEMORY;
    if(c->event_count)memcpy(next,c->events,(size_t)c->event_count*sizeof(e));
    next[c->event_count]=e;POINTS_CATALOG_FREE(c->events);c->events=next;++c->event_count;++c->next_event_id;++c->revision;
    *id=e.id;return POINTS_CATALOG_OK;
}
static inline int points_catalog_update_event(points_catalog *c,const points_catalog_item *draft) {
    if(!points_catalog_valid(c)||!draft)return POINTS_CATALOG_INVALID;
    const points_catalog_item *old=points_catalog_find_event(c,draft->id);
    if(!old)return POINTS_CATALOG_NOT_FOUND;
    if(c->revision==UINT32_MAX||old->revision==UINT32_MAX)return POINTS_CATALOG_EXHAUSTED;
    points_catalog_item e=*draft;e.revision=old->revision+1;
    if(!points_catalog_item_valid(c,&e))return POINTS_CATALOG_INVALID;
    c->events[old-c->events]=e;++c->revision;return POINTS_CATALOG_OK;
}
static inline int points_catalog_delete_event(points_catalog *c,uint32_t id) {
    if(!points_catalog_valid(c))return POINTS_CATALOG_INVALID;
    const points_catalog_item *old=points_catalog_find_event(c,id);
    if(!old)return POINTS_CATALOG_NOT_FOUND;
    if(c->revision==UINT32_MAX)return POINTS_CATALOG_EXHAUSTED;
    size_t at=(size_t)(old-c->events);
    memmove(c->events+at,c->events+at+1,(c->event_count-at-1)*sizeof(*c->events));
    --c->event_count;++c->revision;return POINTS_CATALOG_OK;
}
static inline bool points_catalog_same_name(const char *a,const char *b) {
    while(*a&&*b){unsigned x=(unsigned char)*a++,y=(unsigned char)*b++;
        if(x>='a'&&x<='z')x-=32;
        if(y>='a'&&y<='z')y-=32;
        if(x!=y)return false;}
    return !*a&&!*b;
}
static inline int points_catalog_save_type(points_catalog *c,const points_catalog_type *draft,uint32_t *id) {
    if(id)*id=0;
    if(!id||!points_catalog_valid(c)||!draft)return POINTS_CATALOG_INVALID;
    const points_catalog_type *old=draft->id?points_catalog_find_type(c,draft->id):NULL;
    if(draft->id&&!old)return POINTS_CATALOG_NOT_FOUND;
    if(old&&old->id<=POINTS_BEDTIME)return POINTS_CATALOG_INVALID;
    if(c->revision==UINT32_MAX||(old?old->revision==UINT32_MAX:c->next_type_id==UINT32_MAX))return POINTS_CATALOG_EXHAUSTED;
    points_catalog_type t=*draft;t.id=old?old->id:c->next_type_id;t.revision=old?old->revision+1:1;
    if(!points_catalog_type_valid(&t))return POINTS_CATALOG_INVALID;
    for(uint32_t i=0;i<c->type_count;i++)if(c->types[i].id!=t.id&&points_catalog_same_name(c->types[i].name,t.name))
        return POINTS_CATALOG_INVALID;
    if(old) {
        /* Removing duration support cannot invalidate already saved events. */
        if(!(t.flags&POINTS_TYPE_DURATION))for(uint32_t i=0;i<c->event_count;i++)
            if(c->events[i].type_id==t.id&&(c->events[i].duration_minutes||c->events[i].notify_end||c->events[i].warn3))
                return POINTS_CATALOG_IN_USE;
        c->types[old-c->types]=t;
    } else {
        uint32_t bytes;
        if(c->type_count==UINT32_MAX||!points_catalog_size(c->event_count,c->type_count+1,&bytes)||
           (uint64_t)(c->type_count+1)*sizeof(t)>SIZE_MAX)return POINTS_CATALOG_EXHAUSTED;
        points_catalog_type *next=POINTS_CATALOG_ALLOC((size_t)(c->type_count+1)*sizeof(t));
        if(!next)return POINTS_CATALOG_MEMORY;
        if(c->type_count)memcpy(next,c->types,(size_t)c->type_count*sizeof(t));
        next[c->type_count]=t;POINTS_CATALOG_FREE(c->types);c->types=next;++c->type_count;++c->next_type_id;
    }
    ++c->revision;*id=t.id;return POINTS_CATALOG_OK;
}
static inline int points_catalog_delete_type(points_catalog *c,uint32_t id) {
    if(!points_catalog_valid(c)||id<=POINTS_BEDTIME)return POINTS_CATALOG_INVALID;
    const points_catalog_type *old=points_catalog_find_type(c,id);
    if(!old)return POINTS_CATALOG_NOT_FOUND;
    if(c->revision==UINT32_MAX)return POINTS_CATALOG_EXHAUSTED;
    for(uint32_t i=0;i<c->event_count;i++)if(c->events[i].type_id==id)return POINTS_CATALOG_IN_USE;
    size_t at=(size_t)(old-c->types);memmove(c->types+at,c->types+at+1,(c->type_count-at-1)*sizeof(*c->types));
    --c->type_count;++c->revision;return POINTS_CATALOG_OK;
}
static inline int points_catalog_apply_type(points_catalog_item *event,const points_catalog *c,uint32_t id) {
    const points_catalog_type *t=points_catalog_find_type(c,id);
    if(!event||!t)return POINTS_CATALOG_NOT_FOUND;
    event->type_id=id;event->duration_minutes=t->duration_minutes;event->mode=t->mode;
    event->notify_end=(t->flags&POINTS_TYPE_NOTIFY_END)!=0;event->warn3=(t->flags&POINTS_TYPE_WARN3)!=0;
    return POINTS_CATALOG_OK;
}
#endif
