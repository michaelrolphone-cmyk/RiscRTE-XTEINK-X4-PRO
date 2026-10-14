#pragma once
/* Separate copied view for the filesystem catalog. The legacy
 * PortablePointsState layout and editor/storage capacity are unchanged.
 * This four-row window is presentation data, never the catalog authority. */
#include "PointsCatalogProjection.h"
#include <stdbool.h>
#include <string.h>
typedef points_catalog_event portable_points_catalog_event;
typedef points_catalog_projection portable_points_catalog_view;
static inline bool portable_points_catalog_event_valid(const portable_points_catalog_event *e) {
    if(!e || !e->event_id || !e->type_id || !e->revision || !e->deadline ||
       !e->parent_day || !e->label[0] || e->edge>1 || e->mode>3 || e->symbol>7 || e->reserved[0])return false;
    for(unsigned i=0;i<sizeof(e->label);i++) {
        unsigned c=(unsigned char)e->label[i];
        if(!c)return true;
        if(c<32 || c>126)return false;
    }
    return false;
}
static inline bool portable_points_catalog_view_valid(const portable_points_catalog_view *v) {
    if(!v || v->struct_size<sizeof(*v) || v->count>POINTS_CATALOG_NEXT_COUNT ||
       v->has_previous>1 || v->valid_until<=v->seconds)return false;
    if(v->has_previous && (!portable_points_catalog_event_valid(&v->previous) ||
       v->previous.deadline>v->seconds))return false;
    for(unsigned i=0;i<v->count;i++) {
        if(!portable_points_catalog_event_valid(&v->next[i]) || v->next[i].deadline<=v->seconds ||
           (i && v->next[i].deadline<v->next[i-1].deadline))return false;
    }
    return true;
}
/* Advance an already copied UTC/RTC-second window without provider/storage I/O.
 * A clock rewind or exclusive expiry requires normal-service refresh. */
static inline bool portable_points_catalog_view_at(const portable_points_catalog_view *saved,
                                                  uint32_t seconds,portable_points_catalog_view *out) {
    if(!out || !portable_points_catalog_view_valid(saved) || seconds<saved->seconds ||
       seconds>=saved->valid_until)return false;
    portable_points_catalog_view next=*saved;
    while(next.count && next.next[0].deadline<=seconds) {
        next.previous=next.next[0];next.has_previous=1;next.count--;
        memmove(next.next,next.next+1,next.count*sizeof(next.next[0]));
        memset(&next.next[next.count],0,sizeof(next.next[0]));
    }
    next.seconds=seconds;*out=next;return true;
}
