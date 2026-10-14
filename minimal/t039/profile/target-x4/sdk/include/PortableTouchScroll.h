#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "PortableTouch.h"

/* Fixed storage, logical pixels, and no frame queue. The owner samples input
 * even when display submission is busy, then renders the latest offset once.
 * A viewport is also the hit-test and raster clip; partially visible rows
 * retain their original item identity. No provider or platform dependency. */
typedef struct { int x,y,width,height; } portable_scroll_viewport;
typedef struct {
    portable_scroll_viewport view;
    int extent, count, limit, position_q8, velocity_q8;
    int start_x,start_y,last_x,last_y,start_q8;
    uint32_t sample_ms,moved_ms,animation_ms;
    bool contact,eligible,dragged,vertical,blocked,stop_tap;
} portable_touch_scroll;
enum { PORTABLE_SCROLL_CHANGED=1, PORTABLE_SCROLL_TAP=2,
       PORTABLE_SCROLL_BACK=4 };

static inline int portable_scroll_abs(int n) {return n<0?-n:n;}
static inline int portable_scroll_clamp(int n,int hi) {return n<0?0:n>hi?hi:n;}
static inline int portable_scroll_offset(const portable_touch_scroll *s) {return s->position_q8/256;}
static inline bool portable_scroll_inside(const portable_scroll_viewport *v,int x,int y) {
    return x>=v->x && x<v->x+v->width && y>=v->y && y<v->y+v->height;
}
static inline void portable_scroll_cancel(portable_touch_scroll *s) {
    s->contact=s->eligible=s->dragged=s->vertical=s->stop_tap=false;
    s->velocity_q8=0;s->blocked=true;
}
static inline void portable_scroll_configure(portable_touch_scroll *s,
    portable_scroll_viewport view,int extent,int count) {
    /* Bound all Q8 arithmetic, including untrusted app catalog dimensions. */
    if(view.x < -4096 || view.x>4096 || view.y < -4096 || view.y>4096 ||
       view.width<1 || view.height<1 || view.width>4096 || view.height>4096 ||
       extent<1 || extent>4096 || count<0 || count>1048576/extent) {
        view=(portable_scroll_viewport){0};extent=1;count=0;
    }
    s->view=view;s->extent=extent;s->count=count;
    s->limit=count*extent>view.height?count*extent-view.height:0;
    s->position_q8=portable_scroll_clamp(s->position_q8,s->limit*256);
}
static inline void portable_scroll_reveal(portable_touch_scroll *s,int row) {
    if(row<0 || row>=s->count)return;
    int top=row*s->extent,offset=portable_scroll_offset(s);
    if(top<offset)offset=top;
    else if(top+s->extent>offset+s->view.height)offset=top+s->extent-s->view.height;
    s->position_q8=portable_scroll_clamp(offset,s->limit)*256;
    s->velocity_q8=0;
}
static inline int portable_scroll_row(const portable_touch_scroll *s,int x,int y) {
    if(!portable_scroll_inside(&s->view,x,y))return -1;
    int row=(y-s->view.y+portable_scroll_offset(s))/s->extent;
    return row<s->count?row:-1;
}
static inline int portable_scroll_row_y(const portable_touch_scroll *s,int row) {
    return s->view.y+row*s->extent-portable_scroll_offset(s);
}
static inline bool portable_scroll_clip(const portable_scroll_viewport *v,
    int *x,int *y,int *w,int *h) {
    int right=*x+*w,bottom=*y+*h;
    if(*x<v->x)*x=v->x;
    if(*y<v->y)*y=v->y;
    if(right>v->x+v->width)right=v->x+v->width;
    if(bottom>v->y+v->height)bottom=v->y+v->height;
    *w=right-*x;*h=bottom-*y;return *w>0 && *h>0;
}
static inline bool portable_scroll_animate(portable_touch_scroll *s,uint32_t now) {
    uint32_t dt=now-s->animation_ms;s->animation_ms=now;
    if(s->contact || !s->velocity_q8)return false;
    /* Never replay a hidden/suspended animation or accrue render debt. */
    if(dt>160){s->velocity_q8=0;return false;}
    int before=portable_scroll_offset(s);
    while(dt) {
        unsigned step=dt>16?16:dt;dt-=step;
        int v=s->velocity_q8,decay=(int)step;
        int next=v>0?(v>decay?v-decay:0):(v<-decay?v+decay:0);
        int target=s->position_q8+(v+next)*(int)step/2;
        s->position_q8=portable_scroll_clamp(target,s->limit*256);
        s->velocity_q8=s->position_q8==target?next:0;
    }
    return portable_scroll_offset(s)!=before;
}
static inline unsigned portable_scroll_touch(portable_touch_scroll *s,
    const portable_touch_sample *sample,uint32_t now) {
    int before=portable_scroll_offset(s);unsigned result=0;
    if(!sample->valid || sample->cancelled){portable_scroll_cancel(s);return 0;}
    if(s->blocked) {
        if(!sample->down || (sample->began && sample->tap_eligible))s->blocked=false;
        else return 0;
    }
    /* Snapshot-only providers release at the original down coordinate when
     * there is no queued UP event. The latest observed contact is authoritative. */
    bool snapshot_release=sample->released;
#ifdef PORTABLE_TOUCH_SCROLL
    snapshot_release=snapshot_release && !sample->release_position_valid;
#endif
    int x=snapshot_release?s->last_x:sample->x,y=snapshot_release?s->last_y:sample->y;
    if(sample->began) {
        s->stop_tap=s->velocity_q8!=0;s->velocity_q8=0;
        s->contact=true;s->eligible=sample->tap_eligible;
        s->dragged=s->vertical=false;s->start_x=s->last_x=x;s->start_y=s->last_y=y;
        s->start_q8=s->position_q8;s->sample_ms=s->moved_ms=s->animation_ms=now;
    }
    if(s->contact && (sample->down || sample->released)) {
        int dx=x-s->start_x,dy=y-s->start_y;
        if(!s->dragged && (sample->moved || portable_scroll_abs(dx)+portable_scroll_abs(dy)>=8)) {
            s->dragged=true;
            s->vertical=portable_scroll_abs(dy)>portable_scroll_abs(dx) &&
                portable_scroll_inside(&s->view,s->start_x,s->start_y);
        }
        if(s->vertical) {
            int target=s->start_q8-dy*256;
            s->position_q8=portable_scroll_clamp(target,s->limit*256);
            uint32_t dt=now-s->sample_ms;
            if(y!=s->last_y && dt) {
                int velocity=(s->last_y-y)*256/(int)(dt>160?160:dt);
                if(velocity>1024)velocity=1024;
                if(velocity<-1024)velocity=-1024;
                s->velocity_q8=(s->velocity_q8+velocity)/2;s->moved_ms=now;
            }
            if(s->position_q8!=target)s->velocity_q8=0;
        }
        s->last_x=x;s->last_y=y;s->sample_ms=now;
        if(sample->released) {
            s->contact=false;s->animation_ms=now;
            if(!s->eligible || now-s->moved_ms>80)s->velocity_q8=0;
            if(s->eligible && !s->dragged && !sample->moved && sample->tap_eligible && !s->stop_tap)
                result|=PORTABLE_SCROLL_TAP;
            if(s->eligible && s->dragged && !s->vertical && dx>=44 && dx>portable_scroll_abs(dy)*2)
                result|=PORTABLE_SCROLL_BACK;
        }
    } else if(!sample->down)portable_scroll_animate(s,now);
    if(portable_scroll_offset(s)!=before)result|=PORTABLE_SCROLL_CHANGED;
    return result;
}
