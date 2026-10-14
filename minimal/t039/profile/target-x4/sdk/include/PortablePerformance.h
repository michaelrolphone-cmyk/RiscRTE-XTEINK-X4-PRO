#pragma once
#include <stdbool.h>
#include <stdint.h>
/* App-owned values. Runtime owns phase numbers. Never encode text, addresses,
 * coordinates, preference values, file paths or other user data in records. */

#ifdef PORTABLE_PERFORMANCE_TRACE
enum {
 PORTABLE_PERF_TOUCH_SAMPLE=0x100, PORTABLE_PERF_INPUT_DELIVERED=0x101,
 PORTABLE_PERF_LAUNCH=0x110, PORTABLE_PERF_LAUNCH_FAILED=0x111,
 PORTABLE_PERF_SETTINGS_ACTION=0x200, PORTABLE_PERF_TIMEZONE_PREV=0x201,
 PORTABLE_PERF_TIMEZONE_NEXT=0x202, PORTABLE_PERF_TIMEZONE_SWIPE=0x203,
 PORTABLE_PERF_TIMEZONE_BOUNDARY=0x204, PORTABLE_PERF_TIMEZONE_OPEN=0x205,
 PORTABLE_PERF_SPRINGBOARD_PAGE=0x300, PORTABLE_PERF_CLOCK_LAUNCH=0x400,
 PORTABLE_PERF_SPAN_ACQUIRE=0x1000, PORTABLE_PERF_SPAN_RASTER=0x1001,
 PORTABLE_PERF_SPAN_DAMAGE=0x1002, PORTABLE_PERF_SPAN_SUBMIT=0x1003,
 PORTABLE_PERF_SPAN_PROMOTION=0x1100, PORTABLE_PERF_SPAN_CONFIG=0x1101,
 PORTABLE_PERF_SPAN_LOGO=0x1102, PORTABLE_PERF_SPAN_RECOVERY=0x1103,
 PORTABLE_PERF_SPAN_CLASSIFICATION=0x1104,
 PORTABLE_PERF_SPAN_SETTINGS_DISPATCH=0x1200
};
enum {
 PORTABLE_PERF_INPUT_READS=1, PORTABLE_PERF_NATIVE_READS=2,
 PORTABLE_PERF_KV_READS=3, PORTABLE_PERF_RASTER_PASSES=4,
 PORTABLE_PERF_BATTERY_READS=5, PORTABLE_PERF_STATUS_POLLS=6,
 PORTABLE_PERF_COUNTER_COUNT=7
};
#include "RiscPerformanceV1.h"
void portable_perf_event(uint32_t phase,uint32_t value);
void portable_perf_count(unsigned counter);
void portable_perf_action(uint32_t detail,bool handoff);
void portable_perf_span(uint32_t tag,bool begin);
#else
/* No callback, state, clock sampling or extra dependency in normal builds. */
#define portable_perf_event(phase,value) ((void)0)
#define portable_perf_count(counter) ((void)0)
#define portable_perf_action(detail,handoff) ((void)0)
#define portable_perf_span(tag,begin) ((void)0)
#endif
