#pragma once
/* Private app/client link, never a Runtime/provider ABI or ELF export.
 * PORTABLE_NATIVE_TIME_TOOLBAR selects this single source for shared paper and
 * Quick clocks. The app owns its per-sample reader grant and selected timezone;
 * it closes the grant before returning, or calls portable_adapter_retain() on
 * uncertainty. No grant, callback, provider pointer or snapshot is retained here.
 * On success return already-local Gregorian civil fields (1600..9999), with a
 * correct Sunday=0 weekday; false means unavailable. No RTC fallback occurs. */
#include "PortableRtcClock.h"
#include "PortableNativeCustody.h"
__attribute__((visibility("hidden"))) bool portable_app_native_local_time(twatch_rtc_time_v1 *out);

/* Closed native UTC sample for HTTPS; does not load or apply a timezone. */
__attribute__((visibility("hidden"))) bool portable_app_native_utc_time(int64_t *out);
