/* Exact shared PortableTouch reducer plus real GT911 provider, in separate
 * translation units so each keeps its own SDK. No copied reducer algorithm. */
#include "PortableTouch.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

const risc_touch_api_v1 *multitouch_fixture_start(void);
void multitouch_fixture_report(const risc_touch_contact_v1 *, unsigned, uint64_t);
void multitouch_fixture_ack(bool);
void multitouch_fixture_stop(void);
static const risc_touch_api_v1 *touch;
static unsigned grants;
static bool acquire(const char *name, uint32_t version, uint64_t instance,
                    risc_runtime_capability_v1 *out) {
    assert(!strcmp(name,"input.touch.raw") && version==1 && !instance && !grants);
    assert(out->struct_size==sizeof(*out)); out->api=touch; ++grants; return true;
}
static bool release(risc_runtime_capability_v1 *grant) {
    assert(grants==1 && grant->api==touch); grant->api=NULL; --grants; return true;
}
static const risc_runtime_api_v1 runtime = {
    .api_version=1, .struct_size=sizeof(runtime), .acquire=acquire, .release=release
};
static portable_touch reducer;
static portable_touch_sample edge(void) {
    portable_touch_sample s={0}; assert(portable_touch_next(&reducer,&s)); return s;
}
static void report(unsigned count, uint64_t ms, uint16_t first_x) {
    const risc_touch_contact_v1 points[2]={{.id=1,.x=first_x,.y=100},{.id=8,.x=300,.y=500}};
    multitouch_fixture_report(points,count,ms); assert(touch->poll(NULL,1));
}
static void drain(void) {
    portable_touch_sample s={0}; unsigned n=0;
    while(portable_touch_next(&reducer,&s))assert(++n<64);
    assert(!reducer.terminal && !reducer.resync);
}
static void neutral(uint64_t ms) { report(0,ms,0); drain(); assert(reducer.neutral); }
static void no_action(portable_touch_sample s) {
    assert(!s.began && !s.released && !s.down && !s.home_pressed);
}
static void contact_before_motion(void) {
    report(1,1000,100); portable_touch_sample s=edge(); assert(s.began && s.down);
    /* Add a second finger and move the first past swipe threshold atomically.
     * Then advance the snapshot clock without edges before reducing either. */
    report(2,1001,200); report(2,1002,200);
    s=edge(); assert(s.cancelled); no_action(s);
    s=edge(); no_action(s); assert(!reducer.neutral); drain();
    /* Individual lift cannot rearm the surviving held contact. */
    const risc_touch_contact_v1 held={.id=8,.x=300,.y=500};
    multitouch_fixture_report(&held,1,1003); assert(touch->poll(NULL,1));
    s=edge(); no_action(s); drain(); assert(!reducer.neutral);
    neutral(1004); report(1,1005,110); s=edge(); assert(s.began && s.tap_eligible);
    report(0,1006,0); s=edge(); assert(s.released && s.tap_eligible && !s.moved);
}
static void queued_independent_tap(void) {
    /* The newer two-finger snapshot must not erase an earlier complete tap. */
    report(1,1000,100); report(0,1001,0); report(2,1002,200); report(2,1003,200);
    portable_touch_sample s=edge(); assert(s.began && s.tap_eligible);
    s=edge(); assert(s.released && s.tap_eligible && !s.moved);
    s=edge(); assert(s.began); s=edge(); assert(s.cancelled); no_action(s);
    neutral(1004);
}
static void same_timestamp_edges(void) {
    report(1,1000,100); report(0,1000,0); report(1,1000,120); report(0,1000,0);
    for(unsigned i=0;i<2;++i) {
        portable_touch_sample s=edge(); assert(s.began && s.tap_eligible);
        s=edge(); assert(s.released && s.tap_eligible && !s.moved);
    }
    drain();
}
static void gap_and_ack(void) {
    report(1,1000,100); assert(edge().began);
    for(unsigned i=0;i<34;++i)report(2,1001+i,(uint16_t)(101+i));
    portable_touch_sample s=edge(); assert(s.cancelled); drain();
    assert(!reducer.neutral && !reducer.down); neutral(1040);
    const risc_touch_contact_v1 two[2]={{.id=1,.x=100,.y=100},{.id=8,.x=300,.y=500}};
    multitouch_fixture_report(two,2,1041); multitouch_fixture_ack(false);
    assert(!portable_touch_collect(&reducer));
    /* A failed ACK retains provider edges but must never activate UI. */
    for(unsigned i=0;i<2;++i) { s=edge(); no_action(s); }
    multitouch_fixture_ack(true); assert(portable_touch_collect(&reducer)); drain();
    assert(!reducer.neutral); neutral(1042);
}
int main(int argc,char **argv) {
    assert(argc==2); touch=multitouch_fixture_start();
    assert(portable_touch_open(&reducer,&runtime));
    if(!strcmp(argv[1],"contact-before-motion"))contact_before_motion();
    else if(!strcmp(argv[1],"queued-independent-tap"))queued_independent_tap();
    else if(!strcmp(argv[1],"same-timestamp-edges"))same_timestamp_edges();
    else if(!strcmp(argv[1],"gap-and-ack"))gap_and_ack();
    else abort();
    assert(portable_touch_close(&reducer,&runtime) && !grants);
    multitouch_fixture_stop(); printf("GT911 shared consumer PASS: %s\n",argv[1]);
}
