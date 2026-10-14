#pragma once
/* Explicit schema3 copied catalog window. No event catalog or filesystem I/O.
 * Legacy schema2/128 bytes is documented and tested separately. */
#include "PortablePointsCatalogView.h"
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
enum { PORTABLE_DESK_POINTS_UNAVAILABLE=0, PORTABLE_DESK_POINTS_READY=1,
       PORTABLE_DESK_POINTS_ERROR=2 };
#define PORTABLE_DESK_POINTS_BYTES 328u
#define PORTABLE_DESK_POINTS_EVENT_BYTES 60u
typedef struct { uint8_t status;portable_points_catalog_view view; } portable_desk_points_snapshot;
static inline uint32_t portable_desk_read32(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static inline void portable_desk_write32(uint8_t *p,uint32_t value) {
    for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(value>>(i*8));
}
static inline bool portable_desk_points_valid(const portable_desk_points_snapshot *s) {
    if(!s || s->status>PORTABLE_DESK_POINTS_ERROR)return false;
    return s->status!=PORTABLE_DESK_POINTS_READY || portable_points_catalog_view_valid(&s->view);
}
static inline void portable_desk_points_encode_event(uint8_t *p,const portable_points_catalog_event *e) {
    const uint32_t fields[]={e->event_id,e->type_id,e->revision,e->deadline,e->parent_day,e->color};
    for(unsigned i=0;i<6;i++)portable_desk_write32(p+4*i,fields[i]);
    p[24]=e->edge;p[25]=e->mode;p[26]=e->symbol;
    for(unsigned i=0;i<sizeof(e->label) && e->label[i];i++)p[28+i]=(uint8_t)e->label[i];
}
static inline void portable_desk_points_decode_event(const uint8_t *p,portable_points_catalog_event *e) {
    *e=(portable_points_catalog_event){.event_id=portable_desk_read32(p),.type_id=portable_desk_read32(p+4),
        .revision=portable_desk_read32(p+8),.deadline=portable_desk_read32(p+12),
        .parent_day=portable_desk_read32(p+16),.color=portable_desk_read32(p+20),
        .edge=p[24],.mode=p[25],.symbol=p[26],.reserved={p[27]}};
    memcpy(e->label,p+28,sizeof(e->label));
}
static inline bool portable_desk_points_encode(const portable_desk_points_snapshot *s,uint8_t *out) {
    if(!out || !portable_desk_points_valid(s))return false;
    memset(out,0,PORTABLE_DESK_POINTS_BYTES);
    if(s->status!=PORTABLE_DESK_POINTS_READY)return true;
    const portable_points_catalog_view *v=&s->view;
    const uint32_t fields[]={v->catalog_revision,v->snapshot,v->seconds,v->count,v->flags,v->has_previous,v->valid_until};
    for(unsigned i=0;i<7;i++)portable_desk_write32(out+4*i,fields[i]);
    if(v->has_previous)portable_desk_points_encode_event(out+28,&v->previous);
    for(unsigned i=0;i<v->count;i++)portable_desk_points_encode_event(out+88+i*60,&v->next[i]);
    return true;
}
static inline bool portable_desk_points_decode(uint8_t status,const uint8_t *p,portable_desk_points_snapshot *out) {
    if(!p || !out || status>PORTABLE_DESK_POINTS_ERROR)return false;
    portable_desk_points_snapshot next={.status=status};
    if(status!=PORTABLE_DESK_POINTS_READY) {
        for(unsigned i=0;i<PORTABLE_DESK_POINTS_BYTES;i++)if(p[i])return false;
    } else {
        portable_points_catalog_view *v=&next.view;v->struct_size=sizeof(*v);
        v->catalog_revision=portable_desk_read32(p);v->snapshot=portable_desk_read32(p+4);
        v->seconds=portable_desk_read32(p+8);v->count=portable_desk_read32(p+12);
        v->flags=portable_desk_read32(p+16);v->has_previous=portable_desk_read32(p+20);v->valid_until=portable_desk_read32(p+24);
        portable_desk_points_decode_event(p+28,&v->previous);
        for(unsigned i=0;i<4;i++)portable_desk_points_decode_event(p+88+i*60,&v->next[i]);
        if(!portable_desk_points_valid(&next))return false;
        uint8_t canonical[PORTABLE_DESK_POINTS_BYTES];
        if(!portable_desk_points_encode(&next,canonical) || memcmp(canonical,p,sizeof(canonical)))return false;
    }
    *out=next;return true;
}
