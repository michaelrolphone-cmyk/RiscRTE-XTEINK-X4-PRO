#pragma once
#include "RiscRuntimeV1.h"
#include "RiscTouchV1.h"
#include <string.h>
#ifdef PORTABLE_NATIVE_CUSTODY_FENCE
#include "PortableNativeCustody.h"
#endif
#if defined(PORTABLE_NATIVE_CUSTODY_FENCE) && defined(PORTABLE_STAGE_LOGS)
#define PORTABLE_TOUCH_ISSUE(op,status,terminal) portable_adapter_touch_issue(op,status,terminal)
#else
#define PORTABLE_TOUCH_ISSUE(op,status,terminal) ((void)0)
#endif
#ifndef PORTABLE_TOUCH_ROTATION
#define PORTABLE_TOUCH_ROTATION 0
#endif
#if PORTABLE_TOUCH_ROTATION != 0 && PORTABLE_TOUCH_ROTATION != 180
#error "Portable touch supports explicit 0 or 180 degree deployment rotation"
#endif
static inline void portable_touch_orient(uint16_t width,uint16_t height,uint16_t *x,uint16_t *y) {
#if PORTABLE_TOUCH_ROTATION == 180
  *x=(uint16_t)(width-1-*x);*y=(uint16_t)(height-1-*y);
#else
  (void)width;(void)height;(void)x;(void)y;
#endif
}
/* The provider's per-subscriber queue is the only event queue. These are copied
 * reducer state and an explicit boundary watermark, never borrowed pointers.
 * Initial held input may be adopted as drag-only; faults and reset boundaries
 * suppress inherited contacts until neutral. One app executor serializes calls
 * to collect/next/reset; only the provider queue is shared with other pollers. */
typedef struct {
  risc_runtime_capability_v1 grant;
  const risc_touch_api_v1 *api;
  uint64_t subscription;
  bool neutral, down, moved;
  bool home_neutral, home_down;
  uint16_t x, y;
  uint8_t contact_id;
  bool initialized, terminal, resync, cancel_pending, initial_pending, prefix, poll_failed;
  uint16_t width, height, origin_x, origin_y;
  uint64_t sequence, timestamp_ms;
  uint32_t buttons;
  uint8_t contact_count;
  risc_touch_contact_v1 contacts[RISC_TOUCH_MAX_CONTACTS];
} portable_touch;
typedef struct {
  bool valid, down, began, released, cancelled, tap_eligible, moved;
  uint16_t x, y;
  bool home_pressed;
  /* App-local metadata, not part of the provider ABI. */
  uint8_t contact_id;
  uint64_t timestamp_ms;
#ifdef PORTABLE_TOUCH_SCROLL
  bool release_position_valid;
#endif
} portable_touch_sample;

static inline void portable_touch_terminal(portable_touch *t,const char *op,int status) {
  if(t->terminal)return;
  t->terminal=true;
  PORTABLE_TOUCH_ISSUE(op,status,1);
  (void)op;(void)status;
#ifdef PORTABLE_NATIVE_CUSTODY_FENCE
  portable_adapter_retain();
#endif
}
static inline void portable_touch_fault(portable_touch *t,const char *op,int status) {
  PORTABLE_TOUCH_ISSUE(op,status,0);
  (void)op;(void)status;
  t->cancel_pending|=!t->resync;
  t->neutral=t->down=t->moved=t->home_neutral=t->home_down=false;
  t->initial_pending=false;t->resync=true;
}
static inline bool portable_touch_snapshot_valid(const risc_touch_snapshot_v1 *s) {
  if(!s->width || !s->height || s->contact_count>RISC_TOUCH_MAX_CONTACTS)return false;
  for(unsigned i=0;i<s->contact_count;++i) {
    if(s->contacts[i].x>=s->width || s->contacts[i].y>=s->height)return false;
    for(unsigned j=0;j<i;++j)if(s->contacts[j].id==s->contacts[i].id)return false;
  }
  return true;
}
/* Only startup, an explicit reset boundary, or a discarded faulty stream may
 * adopt a snapshot watermark. Normal reads must first catch up to its sequence. */
static inline bool portable_touch_sync(portable_touch *t,bool initial) {
  risc_touch_snapshot_v1 s={0};
  if(t->terminal || !t->subscription)return false;
  if(!t->api->snapshot(t->api->context,&s)) {
    portable_touch_terminal(t,"snapshot",0);return false;
  }
  if(!portable_touch_snapshot_valid(&s)) {
    portable_touch_fault(t,"snapshot-data",0);return false;
  }
  t->initialized=true;t->resync=false;t->prefix=true;
  t->width=s.width;t->height=s.height;t->sequence=s.sequence;t->timestamp_ms=s.timestamp_ms;
  t->contact_count=s.contact_count;memcpy(t->contacts,s.contacts,sizeof(t->contacts));
  t->buttons=s.buttons;t->home_down=!!(s.buttons&RISC_TOUCH_BUTTON_PRIMARY);
  t->home_neutral=!t->home_down;t->neutral=!s.contact_count;t->moved=false;
  t->down=initial && s.contact_count==1;
  t->initial_pending=t->down;
  if(t->down) {
    t->contact_id=s.contacts[0].id;t->x=t->origin_x=s.contacts[0].x;t->y=t->origin_y=s.contacts[0].y;
  }
  /* A failed poll can leave an older, healthy snapshot behind. It cannot
   * prove neutral until a successful report service and a drained stream. */
  if(t->poll_failed) {t->neutral=t->home_neutral=false;t->resync=true;}
  else PORTABLE_TOUCH_ISSUE(NULL,0,0);
  return true;
}
/* Modal/orientation/invocation boundaries cancel the previous logical gesture.
 * A snapshot-only read captures the boundary before any later collect(). Queued
 * events through that watermark are discarded one at a time by next(); newer
 * events survive. This must not be replaced by direct edits to neutral/down. */
static inline void portable_touch_reset(portable_touch *t) {
  if(t->terminal)return;
  t->neutral=t->down=t->moved=t->home_neutral=t->home_down=false;
  t->initial_pending=false;t->cancel_pending=true;t->resync=true;
  if(t->subscription)(void)portable_touch_sync(t,false);
}
/* Same-owner page changes cancel only the delivered gesture. Unlike reset(),
 * this performs no I/O and preserves every later queued edge and its ordering.
 * A currently held contact stays gated; a delivered UP already proved neutral. */
static inline void portable_touch_cancel_gesture(portable_touch *t) {
  if(t->terminal)return;
  t->down=t->moved=t->initial_pending=false;
  t->neutral=!t->contact_count && !t->resync && !t->poll_failed;
  t->cancel_pending=true;
}
/* Explicit transfer of an INITIAL held contact to an already seeded drag
 * controller. It never arms tapping; the eventual release remains ineligible. */
static inline bool portable_touch_adopt_drag(portable_touch *t) {
  if(t->terminal || t->resync || !t->down || t->contact_count!=1)return false;
  t->neutral=false;t->moved=true;return true;
}
static inline bool portable_touch_open(portable_touch *t,const risc_runtime_api_v1 *r) {
  memset(t,0,sizeof(*t));
  t->grant.struct_size=sizeof(t->grant);
  if(!r->acquire("input.touch.raw",1,0,&t->grant))return false;
  t->api=t->grant.api;
  if(!t->api || t->api->api_version!=1 || t->api->struct_size<sizeof(*t->api) ||
     !t->api->subscribe || !t->api->unsubscribe || !t->api->poll || !t->api->next || !t->api->snapshot)return false;
  t->subscription=t->api->subscribe(t->api->context);
  return t->subscription && portable_touch_sync(t,true);
}
static inline bool portable_touch_close(portable_touch *t,const risc_runtime_api_v1 *r) {
  /* Terminal retention freezes provider/runtime operations, including cleanup. */
  if(t->terminal)return false;
  if(t->subscription && !t->api->unsubscribe(t->api->context,t->subscription)) {
    PORTABLE_TOUCH_ISSUE("unsubscribe",0,1);return false;
  }
  t->subscription=0;
  if(t->grant.api && !r->release(&t->grant)) {
    PORTABLE_TOUCH_ISSUE("release",0,1);return false;
  }
  memset(t,0,sizeof(*t));return true;
}
/* Service hardware without draining or replacing the subscriber's raw edges.
 * A false poll may follow partial progress; next() cancels and safely drains
 * that uncertain interval before checking an authoritative snapshot. */
static inline bool portable_touch_collect(portable_touch *t) {
  if(t->terminal || !t->subscription)return false;
  if(!t->initialized && !portable_touch_sync(t,true))return false;
  if(!t->api->poll(t->api->context,1)) {
    t->poll_failed=true;portable_touch_fault(t,"poll",0);return false;
  }
  t->poll_failed=false;return true;
}
static inline void portable_touch_level(const portable_touch *t,portable_touch_sample *out) {
  out->valid=true;out->down=t->down;out->tap_eligible=t->neutral;out->moved=t->moved;
  out->x=t->x;out->y=t->y;out->contact_id=t->contact_id;out->timestamp_ms=t->timestamp_ms;
  if(t->down)portable_touch_orient(t->width,t->height,&out->x,&out->y);
}
static inline int portable_touch_find(const portable_touch *t,uint8_t id) {
  for(unsigned i=0;i<t->contact_count;++i)if(t->contacts[i].id==id)return (int)i;
  return -1;
}
static inline void portable_touch_move(portable_touch *t,uint16_t x,uint16_t y) {
  int dx=(int)x-t->origin_x,dy=(int)y-t->origin_y;
  unsigned ax=(unsigned)(dx<0?-dx:dx),ay=(unsigned)(dy<0?-dy:dy);
  if(ax+ay>=6u)t->moved=true;
  t->x=x;t->y=y;
}
static inline bool portable_touch_snapshot_matches(const portable_touch *t,const risc_touch_snapshot_v1 *s) {
  if(t->width!=s->width || t->height!=s->height || t->buttons!=s->buttons || t->contact_count!=s->contact_count)return false;
  for(unsigned i=0;i<s->contact_count;++i) {
    int at=portable_touch_find(t,s->contacts[i].id);
    if(at<0 || t->contacts[at].x!=s->contacts[i].x || t->contacts[at].y!=s->contacts[i].y)return false;
  }
  return true;
}
/* Returns true when an edge, cancellation, or initial held sample progressed;
 * false means no stream progress, but out still contains the current level.
 * Each call consumes at most ONE raw edge. No look-ahead or secondary queue is
 * needed: callers may schedule another zero-wait pass after true. */
static inline bool portable_touch_next(portable_touch *t,portable_touch_sample *out) {
  memset(out,0,sizeof(*out));
  if(t->terminal || !t->subscription) {out->cancelled=true;return false;}
  if(!t->initialized && !portable_touch_sync(t,true)) {out->cancelled=true;return false;}
  if(t->cancel_pending && !t->resync) {t->cancel_pending=false;out->cancelled=true;return true;}
  if(t->initial_pending) {
    t->initial_pending=false;portable_touch_level(t,out);out->began=true;return true;
  }
  bool cancelled=t->cancel_pending;t->cancel_pending=false;
  risc_touch_event_v1 e={0};
  int n=t->api->next(t->api->context,t->subscription,&e);
  if(n < -1) {portable_touch_terminal(t,"next",n);out->cancelled=true;return false;}
  if(n==-1) {
    portable_touch_fault(t,"next",n);
    (void)portable_touch_sync(t,false);
    t->cancel_pending=false;out->cancelled=true;return !t->terminal;
  }
  if(!n) {
    if(t->resync) {
      bool okay=portable_touch_sync(t,false);
      if(!okay) {t->cancel_pending=false;out->cancelled=true;return false;}
      if(cancelled) {out->cancelled=true;return true;}
      portable_touch_level(t,out);return false;
    }
    risc_touch_snapshot_v1 s={0};
    if(!t->api->snapshot(t->api->context,&s)) {
      portable_touch_terminal(t,"snapshot",0);out->cancelled=true;return false;
    }
    /* Another subscriber may have polled between next(empty) and snapshot().
     * Leave our older reducer state untouched until its queued edges arrive. */
    if(s.sequence>t->sequence) {portable_touch_level(t,out);return false;}
    t->prefix=false;
    if(s.sequence<t->sequence || !portable_touch_snapshot_valid(&s) ||
       !portable_touch_snapshot_matches(t,&s) || s.timestamp_ms<t->timestamp_ms) {
      portable_touch_fault(t,"snapshot-data",0);t->cancel_pending=false;out->cancelled=true;return true;
    }
    t->timestamp_ms=s.timestamp_ms;portable_touch_level(t,out);return false;
  }
  if(t->resync || (t->prefix && e.sequence<=t->sequence)) {
    out->cancelled=true;return true;
  }
  t->prefix=false;
  if(t->sequence==UINT64_MAX || e.sequence!=t->sequence+1u || e.timestamp_ms<t->timestamp_ms) {
    portable_touch_fault(t,"event-sequence",n);t->cancel_pending=false;out->cancelled=true;return true;
  }
  t->sequence=e.sequence;t->timestamp_ms=e.timestamp_ms;
  int at=-1;
  if(e.kind==RISC_TOUCH_EVENT_BUTTON_DOWN || e.kind==RISC_TOUCH_EVENT_BUTTON_UP) {
    if(e.id>=32u)goto malformed;
    uint32_t bit=(uint32_t)1u<<e.id;
    bool pressed=e.kind==RISC_TOUCH_EVENT_BUTTON_DOWN;
    if(pressed==!!(t->buttons&bit))goto malformed;
    if(pressed)t->buttons|=bit;else t->buttons&=~bit;
    portable_touch_level(t,out);
    if(e.id==0) {
      out->home_pressed=pressed && t->home_neutral && !t->home_down;
      t->home_down=pressed;if(!pressed)t->home_neutral=true;
    }
    return true;
  }
  if(e.x>=t->width || e.y>=t->height)goto malformed;
  at=portable_touch_find(t,e.id);
  if(e.kind==RISC_TOUCH_EVENT_DOWN) {
    if(at>=0 || t->contact_count==RISC_TOUCH_MAX_CONTACTS)goto malformed;
    t->contacts[t->contact_count++]=(risc_touch_contact_v1){.id=e.id,.x=e.x,.y=e.y};
    if(t->contact_count>1) {
      PORTABLE_TOUCH_ISSUE("contact-replaced",0,0);
      t->neutral=t->down=t->moved=false;out->cancelled=true;return true;
    }
    if(t->neutral) {
      t->down=true;t->moved=false;t->contact_id=e.id;
      t->x=t->origin_x=e.x;t->y=t->origin_y=e.y;
      portable_touch_level(t,out);out->began=true;
    }else portable_touch_level(t,out);
    return true;
  }
  if(e.kind==RISC_TOUCH_EVENT_MOVE) {
    /* A provider may list an existing finger's MOVE before a new finger's
     * DOWN in one report. Do not expose that ambiguous motion as a swipe.
     * This reads no event ahead and never adopts a snapshot watermark: later
     * ordered edges, including independent taps, are still consumed normally. */
    if(t->down && t->neutral) {
      risc_touch_snapshot_v1 latest={0};
      if(!t->api->snapshot(t->api->context,&latest)) {
        portable_touch_terminal(t,"snapshot",0);out->cancelled=true;return false;
      }
      if(latest.sequence>e.sequence && latest.timestamp_ms==e.timestamp_ms &&
         latest.contact_count>1 && portable_touch_snapshot_valid(&latest)) {
        t->down=t->neutral=t->moved=false;
        if(at<0)goto malformed;
        t->contacts[at].x=e.x;t->contacts[at].y=e.y;
        out->cancelled=true;return true;
      }
    }
    if(at<0)goto malformed;
    t->contacts[at].x=e.x;t->contacts[at].y=e.y;
    if(t->down && e.id==t->contact_id)portable_touch_move(t,e.x,e.y);
    portable_touch_level(t,out);return true;
  }
  if(e.kind==RISC_TOUCH_EVENT_UP) {
    if(at<0)goto malformed;
    bool released=t->down && e.id==t->contact_id;
    if(released)portable_touch_move(t,e.x,e.y);
    portable_touch_level(t,out);out->down=false;out->released=released;
#ifdef PORTABLE_TOUCH_SCROLL
    out->release_position_valid=released;
#endif
    if(released)t->down=false;
    for(unsigned i=(unsigned)at+1u;i<t->contact_count;++i)t->contacts[i-1u]=t->contacts[i];
    if(!--t->contact_count) {t->neutral=true;PORTABLE_TOUCH_ISSUE(NULL,0,0);}
    return true;
  }
malformed:
  portable_touch_fault(t,"event-data",(int)e.kind);t->cancel_pending=false;out->cancelled=true;return true;
}
/* Compatibility entry point, deliberately identical to collect + next.
 * Compatibility covers the call shape, not the old snapshot-coalescing cadence:
 * a report containing contact and Home edges takes separate calls. Consumers
 * must honor cancellation and keep advancing logical input independently of
 * frame submission. New loops use next() progress to drain without sleeping. */
static inline void portable_touch_read(portable_touch *t,portable_touch_sample *out) {
  (void)portable_touch_collect(t);(void)portable_touch_next(t,out);
}
static inline bool portable_touch_tap(portable_touch *t,uint16_t *x,uint16_t *y) {
  portable_touch_sample s;portable_touch_read(t,&s);
  if(!s.released || !s.tap_eligible || s.moved || s.cancelled)return false;
  *x=s.x;*y=s.y;return true;
}
