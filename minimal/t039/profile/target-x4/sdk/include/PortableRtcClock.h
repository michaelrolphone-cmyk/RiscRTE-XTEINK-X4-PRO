#pragma once
/* Consumer-only copy of the existing rtc.clock@2 declaration, verbatim below.
 * Source: michaelrolphone-cmyk/RiscRTE-T-Watch-S3 include/twatch_caps.h
 * Commit: 79cbca2cdc216ba1cc280b99856c646d72d9f58c.
 * This does not promote the board-local interface into a canonical SDK or
 * change its ABI. See ../RTC_PROVENANCE.json and the target layout assertions.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* BEGIN VERBATIM RTC DECLARATION */
#define TWATCH_RTC_API_V1 2u
#define TWATCH_RTC_CAPABILITY "rtc.clock"
typedef struct {
    uint16_t year;
    uint8_t month, day, weekday, hour, minute, second;
} twatch_rtc_time_v1;
typedef struct {
    uint32_t api_version, struct_size;
    void *context;
    bool (*read)(void *context, twatch_rtc_time_v1 *out);
    bool (*write)(void *context, const twatch_rtc_time_v1 *in);
    bool (*alarm)(void *, uint8_t minute, uint8_t hour, uint8_t day, uint8_t weekday, bool enable);
    bool (*alarm_pending)(void *, bool *pending, bool acknowledge);
} twatch_rtc_api_v1;
/* END VERBATIM RTC DECLARATION */
_Static_assert(sizeof(twatch_rtc_time_v1) == 8, "rtc.clock@2 calendar size");
_Static_assert(offsetof(twatch_rtc_time_v1, second) == 7, "rtc.clock@2 calendar layout");
#if UINTPTR_MAX == UINT32_MAX
_Static_assert(sizeof(twatch_rtc_api_v1) == 28, "rtc.clock@2 target table size");
_Static_assert(offsetof(twatch_rtc_api_v1, context) == 8, "rtc.clock@2 target context");
_Static_assert(offsetof(twatch_rtc_api_v1, read) == 12, "rtc.clock@2 target read");
_Static_assert(offsetof(twatch_rtc_api_v1, write) == 16, "rtc.clock@2 target write");
_Static_assert(offsetof(twatch_rtc_api_v1, alarm) == 20, "rtc.clock@2 target alarm");
_Static_assert(offsetof(twatch_rtc_api_v1, alarm_pending) == 24, "rtc.clock@2 target alarm status");
#endif
