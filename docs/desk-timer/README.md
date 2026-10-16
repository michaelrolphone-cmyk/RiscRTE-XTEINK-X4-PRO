# Delivered X4 desk-clock timer qualification

This outcome is already implemented in the released X4 0.1.122 Home. The
qualification on 2026-10-16 found no missing timer-wake implementation or
confirmed software regression. This change adds repeatable proof and does not
replace firmware, applications, providers, partitions or saved data.
It also corrects the build receipt to include the compiler wrapper's existing
`PORTABLE_ALARM_BUSY_DEFER` define, so host qualification receives the actual
target profile. This metadata correction does not change the compiled ELF.

## Exact delivered identity

The 0.1.122 native SDK migration preserves the 0.1.121 Home application:

- Package: `paper_clock` 0.4.19; `default.elf`, 576,348 bytes
- ELF SHA256: `02b38ed65e1adcb8ecd49c0dc6b58f678ea0110160e38f4f70ed61c5e0b484d7`
- System application source: `09400a550562ca9568ac7ab664ba3222eeedf2c8`
- Home build Runtime tooling: `a91edf3fada6a559ec107186dd163d0c8da10d29`
- Reader SDK/tooling: `c98e4222048244b1e729869ed47aa99130025fd3`
- Utilities: `dcbad832cff91f7988a8e43d84725650b9815953`
- Home compiler: Xtensa ESP32-S3 8.4.0, 2021r2-patch5
- X4 product source: `608f43ec30fd97644b4cb63706251c8e8a0b11f9`
- Released native Runtime: `659d859acb122640ef4003bb8d7099501d4381be`

Re-running `minimal/recovery-107/build_clock.py` with those original Home inputs
reproduces the published ELF SHA256 exactly. The native SDK build's newer System
source role is not the source used to compile this unchanged Home. The legacy
Arduino Reader `DeskClockSleep.cpp` is also a different implementation.

## Scope and measured checks

The actual delivered controller classifies a retained TIMER record before
foreground startup, reconstructs its previous frame, reads native realtime,
updates the displayed minute, stages the 408-byte record, closes mounted SD,
and enters terminal deep sleep. GPIO/ordinary refused wakes return through
foreground promotion. The product sleep-hook SHA256 remains
`0858a85e56bb12ef1255b02eeb5fb3618a4e46fd283e0a369f4f3bffefe0462b`.

Passed locally:

- Exact target ELF reproduction and target loader structural/import validation
- 148 normal/ASan+UBSan sparse lifecycle and RTC-render comparisons, including
  six faces, +/-300-second native-clock drift, GPIO and ordinary foreground
  return, invalid time policy, refusal, retained failures and minute crossings
- 64 full selected-profile timer cases, schema 3, both orientations, synchronous
  and asynchronous display, copied-catalog expiry/rewind, fresh-process reuse,
  terminal fences, mounted-SD closure and no foreground-service activation
- 896 additional fresh-process injected-minute updates: all seven faces, both
  orientations, 32 supplied next-minute samples each, exact +60-second rendering,
  changed pixels, and crossing the 30-update refresh counter. Normal and
  ASan+UBSan pixels and retained records are byte-identical
- 1,144 legacy-schema product sleep-client fault/cancellation cases across
  normal and ASan+UBSan, brightness and diagnostics profiles. This separate
  schema-1 compatibility suite is not substituted for the selected schema-3 proof
- Actual released Runtime retained-wake/CpuPort tests and 19 native reset/wake
  classification cases, normal and ASan+UBSan, with 512 retained bytes and
  24 policy rows
- Actual released Runtime deep/timed sleep, owned wake-set, native SDK adapters,
  partial rollback, terminal retention and fresh-process lifecycle, normal and
  ASan+UBSan builds

The optional older sleep-client script's catalog lane references a historical
Utilities object without its requested Alarm header. That lane was not counted
as a pass; the exact selected schema-3 composition is independently covered above.

## Repeatable regression

`.github/workflows/desk-timer-qualification.yml` reproduces the exact Home, runs
the existing full selected-profile test, then executes
`minimal/test/qualify_desk_timer_progression.py`. The runner validates all
recorded source hashes before reusing the unchanged normal/sanitized fixture
binaries. It saves measured minute, refresh counter, pixel and record hashes.
The workflow also repeats normal/sanitized RTC recovery checks.
The progression runner checks retained counters, not actual CLEAN submission
intent. Its fixture supplies each next-minute RTC sample and bounds the sleep
request to 1..60,000 ms; the runner does not prove the exact programmed interval.

Compact local logs and receipts are in `evidence/`. Full per-process receipts
are produced by the workflow artifact. Native runtime gates use the released
Runtime source rather than the newer shared Runtime development branch.

## Limits

These are source/target-build and host composition results with synthetic
provider and sleep callbacks. No physical device was flashed or tested.
Overnight hardware drift, panel current, actual minute-wake reliability and
deployed bootloader compatibility remain unmeasured. No physical pass is claimed.
