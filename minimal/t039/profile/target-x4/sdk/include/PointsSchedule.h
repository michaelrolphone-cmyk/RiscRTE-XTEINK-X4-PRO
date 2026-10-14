#ifndef UTILITIES_POINTS_SCHEDULE_H
#define UTILITIES_POINTS_SCHEDULE_H
#include "PointsRecords.h"
#include "PortableTime.h"
#define POINTS_FLAG_GAP 1u
#define POINTS_FLAG_FOLD 2u
#define POINTS_FLAG_RANGE 4u
#define POINTS_NEXT_COUNT 4u
typedef struct { uint32_t deadline,parent_day; uint8_t slot,edge,kind,mode; } points_event;
typedef struct { points_event previous,next[POINTS_NEXT_COUNT]; uint32_t count,flags; bool has_previous; } points_projection;
static inline bool points_calendar(uint32_t seconds,twatch_rtc_time_v1 *out) {
    if(!out||seconds>ALARM_RTC_MAX)return false;
    uint32_t days=seconds/86400;unsigned y=2000,m=1;
    while(y<2099&&days>=(y%4?365u:366u)){days-=y%4?365u:366u;++y;}
    while(m<12&&days>=watch_month_days(y,m)){days-=watch_month_days(y,m);++m;}
    *out=(twatch_rtc_time_v1){(uint16_t)y,(uint8_t)m,(uint8_t)(days+1),(uint8_t)watch_weekday(y,m,days+1),
        (uint8_t)(seconds/3600%24),(uint8_t)(seconds/60%60),(uint8_t)(seconds%60)};return true;
}
static inline bool points_local_day(uint32_t raw,uint32_t *day) {
    twatch_rtc_time_v1 r,l;uint32_t seconds;
    if(!day||!points_calendar(raw,&r)||!portable_time_forward(&r,&l)||
       !alarm_calendar_seconds(l.year,l.month,l.day,0,0,0,&seconds))return false;
    *day=seconds/86400+1;return true;
}
static inline bool points_notice_enabled(const points_item *p,unsigned edge) {
    if(!p||!p->enabled||edge>=POINTS_EDGE_COUNT)return false;
    if(edge==POINTS_EDGE_START)return true;
    if(edge==POINTS_EDGE_END)return p->duration_minutes&&p->notify_end;
    return p->duration_minutes>=3&&p->warn3;
}
/* End remains a projection edge even when notify_end is disabled. Warning is
 * service-only and occurs exactly three elapsed minutes before the duration end. */
static inline bool points_event_for_day(const points_config *c,unsigned slot,uint32_t parent_day,
                                        unsigned edge,points_event *out,uint32_t *flags) {
    if(!c||!out||slot>=POINTS_MAX||edge>=POINTS_EDGE_COUNT||!parent_day||parent_day>36525)return false;
    const points_item *p=&c->points[slot];twatch_rtc_time_v1 civil;
    if(!p->enabled||!points_calendar((parent_day-1)*86400,&civil)||!(p->weekdays&(1u<<civil.weekday))||
       ((edge==POINTS_EDGE_END||edge==POINTS_EDGE_WARNING)&&!p->duration_minutes)||
       (edge==POINTS_EDGE_WARNING&&!p->warn3))return false;
    civil.hour=p->hour;civil.minute=p->minute;civil.second=0;
    portable_time_candidate candidates[2];unsigned count=portable_time_inverse(&civil,candidates);
    if(count!=1){if(flags)*flags|=count==2?POINTS_FLAG_FOLD:POINTS_FLAG_GAP;return false;}
    twatch_rtc_time_v1 *r=&candidates[0].rtc;uint32_t start;
    if(!alarm_calendar_seconds(r->year,r->month,r->day,r->hour,r->minute,r->second,&start)||
       start>ALARM_RTC_MAX-ALARM_RECOVERY_SECONDS-(uint32_t)p->duration_minutes*60){if(flags)*flags|=POINTS_FLAG_RANGE;return false;}
    if(start<=c->created)return false;
    uint32_t deadline=start;
    if(edge==POINTS_EDGE_END)deadline+=(uint32_t)p->duration_minutes*60;
    else if(edge==POINTS_EDGE_WARNING)deadline+=(uint32_t)p->duration_minutes*60-180u;
    *out=(points_event){deadline,parent_day,(uint8_t)slot,(uint8_t)edge,p->kind,p->mode};return true;
}
static inline bool points_event_before(const points_event *a,const points_event *b) {
    return a->deadline<b->deadline||(a->deadline==b->deadline&&points_token_kind(a->slot,a->edge)<points_token_kind(b->slot,b->edge));
}
static inline bool points_project(const points_config *c,uint32_t now,points_projection *out) {
    if(!c||!out)return false;
    memset(out,0,sizeof(*out));uint32_t today;
    if(!c->revision)return true;
    if(!points_config_valid(c)||!points_local_day(now,&today)){out->flags=POINTS_FLAG_RANGE;return false;}
    for(int offset=-7;offset<=8;offset++) {
        int day=(int)today+offset;if(day<1||day>36525)continue;
        for(unsigned slot=0;slot<POINTS_MAX;slot++)for(unsigned edge=0;edge<2;edge++) {
            points_event e;if(!points_event_for_day(c,slot,(uint32_t)day,edge,&e,offset>=0?&out->flags:NULL))continue;
            if(e.deadline<=now){if(!out->has_previous||points_event_before(&out->previous,&e)){out->previous=e;out->has_previous=true;}}
            else{unsigned at=0;while(at<out->count&&!points_event_before(&e,&out->next[at]))at++;
                if(at<POINTS_NEXT_COUNT){unsigned n=out->count<POINTS_NEXT_COUNT?out->count++:POINTS_NEXT_COUNT-1;while(n>at){out->next[n]=out->next[n-1];n--;}out->next[at]=e;}}
        }
    }return true;
}
static inline bool points_latest_for_edge(const points_config *c,const points_ledger *l,uint32_t now,
                                          unsigned slot,unsigned edge,points_event *out) {
    uint32_t today;if(!c||!c->revision||!l||!out||slot>=POINTS_MAX||edge>=POINTS_EDGE_COUNT||
       !points_notice_enabled(&c->points[slot],edge)||!points_local_day(now,&today))return false;
    bool found=false;
    for(int offset=-8;offset<=0;offset++) {
        int day=(int)today+offset;if(day<1||points_ledger_handled(l,slot,(uint32_t)day,edge))continue;
        points_event e;if(points_event_for_day(c,slot,(uint32_t)day,edge,&e,NULL)&&e.deadline<=now&&(!found||points_event_before(out,&e))){*out=e;found=true;}
    }return found;
}
static inline bool points_due(const points_config *c,const points_ledger *l,uint32_t now,points_event *out) {
    if(!c||!l||!out)return false;
    bool found=false;
    for(unsigned slot=0;slot<POINTS_MAX;slot++)for(unsigned edge=0;edge<POINTS_EDGE_COUNT;edge++) {
        points_event latest;if(points_latest_for_edge(c,l,now,slot,edge,&latest)&&(!found||points_event_before(&latest,out))){*out=latest;found=true;}
    }return found;
}
#endif
