#pragma once
/* App-local policy, selected explicitly by deployment at build time. Identity
 * is the default. No runtime ABI, global TZ state, NTP, or persistent prefs. */
#include "../time/denver/display_time.h"

typedef struct {
  twatch_rtc_time_v1 rtc;
  int16_t utc_offset_minutes; /* Display offset; -360 MDT or -420 MST. */
} portable_time_candidate;

static inline bool portable_time_forward(const twatch_rtc_time_v1 *rtc,
                                         twatch_rtc_time_v1 *display) {
#ifdef PORTABLE_RTC_UTC8_DENVER
  return watch_display_time(rtc, display);
#else
  if (!display || !tw_valid_time(rtc)) return false;
  *display = *rtc;
  return true;
#endif
}
static inline const char *portable_time_zone(void) {
#ifdef PORTABLE_RTC_UTC8_DENVER
  return "America/Denver";
#else
  return "RTC wall time";
#endif
}
static inline const char *portable_time_basis(void) {
#ifdef PORTABLE_RTC_UTC8_DENVER
  return "Fixed UTC+08";
#else
  return "Unconverted";
#endif
}
static inline bool portable_time_same(const twatch_rtc_time_v1 *a,
                                      const twatch_rtc_time_v1 *b) {
  return a->year == b->year && a->month == b->month && a->day == b->day &&
         a->hour == b->hour && a->minute == b->minute && a->second == b->second;
}
static inline bool portable_time_add_hours(const twatch_rtc_time_v1 *in,
                                           unsigned hours, twatch_rtc_time_v1 *out) {
  if (!out || !tw_valid_time(in) || hours > 24) return false;
  *out = *in;
  unsigned hour = out->hour + hours;
  if (hour >= 24) {
    hour -= 24;
    if (++out->day > watch_month_days(out->year, out->month)) {
      out->day = 1;
      if (++out->month > 12) { out->month = 1; ++out->year; }
    }
  }
  out->hour = (uint8_t)hour;
  if (!tw_valid_time(out)) return false;
  out->weekday = (uint8_t)watch_weekday(out->year, out->month, out->day);
  return true;
}
/* A gap/out-of-range civil time returns zero. A fold returns two candidates in
 * time order and REQUIRES an explicit choice. Never choose using current time.
 * The same verified forward converter adjudicates both possible offsets. */
static inline unsigned portable_time_inverse(const twatch_rtc_time_v1 *local,
                                              portable_time_candidate out[2]) {
  if (!out || !tw_valid_time(local)) return 0;
#ifndef PORTABLE_RTC_UTC8_DENVER
  out[0].rtc = *local;
  out[0].rtc.weekday = (uint8_t)watch_weekday(local->year, local->month, local->day);
  out[0].utc_offset_minutes = 0;
  return 1;
#else
  unsigned count = 0;
  for (unsigned i = 0; i < 2; ++i) {
    twatch_rtc_time_v1 rtc, round_trip;
    if (portable_time_add_hours(local, 14 + i, &rtc) &&
        portable_time_forward(&rtc, &round_trip) && portable_time_same(local, &round_trip)) {
      out[count].rtc = rtc;
      out[count].utc_offset_minutes = i ? -420 : -360;
      ++count;
    }
  }
  return count;
#endif
}
