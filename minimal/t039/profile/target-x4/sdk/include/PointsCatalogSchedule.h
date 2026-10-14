#ifndef UTILITIES_POINTS_CATALOG_SCHEDULE_H
#define UTILITIES_POINTS_CATALOG_SCHEDULE_H
#include "PointsCatalogLedger.h"
#include "PointsSchedule.h"
#ifdef ALARM_NATIVE_UTC
#include "PointsUtcSchedule.h"
#endif
#include "PointsCatalogProjection.h"
#ifdef ALARM_NATIVE_UTC
#define POINTS_RULE_ARGUMENT const portable_timezone_rule *rule,
#define POINTS_RULE_PASS rule,
#else
#define POINTS_RULE_ARGUMENT
#define POINTS_RULE_PASS
#endif
static inline bool points_catalog_local_day(POINTS_RULE_ARGUMENT uint32_t now,uint32_t *day) {
#ifdef ALARM_NATIVE_UTC
    return points_utc_local_day(rule,now,day);
#else
    return points_local_day(now,day);
#endif
}
static inline bool points_catalog_notice_enabled(const points_catalog_item *e,unsigned edge) {
    return e&&e->enabled&&edge<3&&(edge==0||(edge==1?e->duration_minutes&&e->notify_end:e->duration_minutes>=3&&e->warn3));
}
/* Reuse the verified raw-RTC/UTC civil inverse, gap/fold and elapsed-duration
 * policies with an isolated one-entry record. Type identity is copied below. */
static inline bool points_catalog_event_for_day(POINTS_RULE_ARGUMENT const points_catalog *c,uint32_t id,uint32_t day,
                                               unsigned edge,points_catalog_event *out,uint32_t *flags) {
    const points_catalog_item *e=points_catalog_find_event(c,id);if(!e||!out)return false;
    points_config one={.revision=e->revision,.created=e->created};
    one.points[0]=(points_item){.kind=POINTS_CUSTOM_1,.enabled=e->enabled,.mode=e->mode,.weekdays=e->weekdays,
        .hour=e->hour,.minute=e->minute,.duration_minutes=e->duration_minutes,.notify_end=e->notify_end,.warn3=e->warn3};
    points_event event;
#ifdef ALARM_NATIVE_UTC
    if(!points_utc_event_for_day(rule,&one,0,day,edge,&event,flags))return false;
#else
    if(!points_event_for_day(&one,0,day,edge,&event,flags))return false;
#endif
    const points_catalog_type *type=points_catalog_find_type(c,e->type_id);if(!type)return false;
    *out=(points_catalog_event){.event_id=id,.type_id=e->type_id,.revision=e->revision,.deadline=event.deadline,
        .parent_day=day,.edge=(uint8_t)edge,.mode=e->mode,.color=type->color,.symbol=type->symbol};
    memcpy(out->label,type->name,sizeof(out->label));return true;
}
static inline bool points_catalog_event_before(const points_catalog_event *a,const points_catalog_event *b) {
    return a->deadline<b->deadline||(a->deadline==b->deadline&&
        (a->event_id<b->event_id||(a->event_id==b->event_id&&a->edge<b->edge)));
}
static inline bool points_catalog_latest_for_edge(POINTS_RULE_ARGUMENT const points_catalog *c,const points_catalog_ledger *l,
                                                 uint32_t now,uint32_t id,unsigned edge,points_catalog_event *out) {
    const points_catalog_item *e=points_catalog_find_event(c,id);uint32_t today;
    if(!out||!points_catalog_notice_enabled(e,edge)||!points_catalog_local_day(POINTS_RULE_PASS now,&today))return false;
    bool found=false;
    for(int offset=-8;offset<=0;offset++) {int day=(int)today+offset;
        if(day<1||points_catalog_ledger_handled(l,id,(uint32_t)day,edge))continue;
        points_catalog_event event;
        if(points_catalog_event_for_day(POINTS_RULE_PASS c,id,(uint32_t)day,edge,&event,NULL)&&event.deadline<=now&&
           (!found||points_catalog_event_before(out,&event))){*out=event;found=true;}}
    return found;
}
static inline bool points_catalog_due(POINTS_RULE_ARGUMENT const points_catalog *c,const points_catalog_ledger *l,
                                      uint32_t now,points_catalog_event *out) {
    bool found=false;
    for(uint32_t i=0;i<c->event_count;i++)for(unsigned edge=0;edge<3;edge++) {
        points_catalog_event e;
        if(points_catalog_latest_for_edge(POINTS_RULE_PASS c,l,now,c->events[i].id,edge,&e)&&
           (!found||points_catalog_event_before(&e,out))){*out=e;found=true;}}
    return found;
}
static inline bool points_catalog_project(POINTS_RULE_ARGUMENT const points_catalog *c,uint32_t now,points_catalog_projection *out) {
    if(!out||!points_catalog_valid(c))return false;
    memset(out,0,sizeof(*out));out->struct_size=sizeof(*out);out->catalog_revision=c->revision;out->seconds=now;
    uint32_t today;if(!points_catalog_local_day(POINTS_RULE_PASS now,&today)){out->flags=POINTS_FLAG_RANGE;return false;}
    for(int offset=-7;offset<=8;offset++) {int day=(int)today+offset;if(day<1||day>36525)continue;
        for(uint32_t i=0;i<c->event_count;i++)for(unsigned edge=0;edge<2;edge++) {
            points_catalog_event e;
            if(!points_catalog_event_for_day(POINTS_RULE_PASS c,c->events[i].id,(uint32_t)day,edge,&e,offset>=0?&out->flags:NULL))continue;
            if(e.deadline<=now){if(!out->has_previous||points_catalog_event_before(&out->previous,&e)){out->previous=e;out->has_previous=1;}}
            else {uint32_t at=0;while(at<out->count&&!points_catalog_event_before(&e,&out->next[at]))at++;
                if(at<POINTS_CATALOG_NEXT_COUNT){uint32_t n=out->count<POINTS_CATALOG_NEXT_COUNT?out->count++:POINTS_CATALOG_NEXT_COUNT-1;
                    while(n>at){out->next[n]=out->next[n-1];--n;}out->next[at]=e;}}
        }}
    /* Cached rows may be advanced only before this exclusive boundary. */
    out->valid_until=out->count==POINTS_CATALOG_NEXT_COUNT?out->next[out->count-1].deadline:
        (now>ALARM_RTC_MAX-7u*86400u?ALARM_RTC_MAX:now+7u*86400u);
    return true;
}
#endif
