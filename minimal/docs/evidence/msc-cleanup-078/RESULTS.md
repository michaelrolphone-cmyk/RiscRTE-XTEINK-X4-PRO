# X4 .1.78 MSC cleanup source checkpoint

The selected source and byte-identical MSC artifact are bound in
[source-binding.json](source-binding.json). The candidate changes only the shared
MSC transport restore comparison, package version and focused tests/docs.
The existing X4 lock and historic build receipts remain unchanged: this is a
proposed source override, not a claim that .1.78 already contains the fix.

## Demonstrated cause and fix

A production stop/wait-body MMIO test fails against pinned Reader 45cf61ac for
saved test_conf=0x05 / observed=0x75, with successful reset and no timeout.
ESP32-S3 IDF 4.4.7 marks bits 4–6 read-only receive status; the comparison must
check only writable bits 0–3. The SDK header used by the test is byte-identical
to the local IDF v4.4.7 source header. Every other shutdown check stays intact.
Reader candidate 4c2e2dbe3bf587b51873c65a1a1c3faf4035e884 fixes that comparison
and increments usb-device-msc-esp32s3 from 0.1.5 to 0.1.6.

## Executed host checks

- Production stop/wait regression: old source fails, candidate passes, including
  1,024 receive/control combinations, every control-bit mismatch, reset/AHB-idle,
  pad/wrap/clock failures, retry and idempotent stop. UBSan passes.
- 48 production provider/TinyUSB owner scenarios pass normally and with UBSan
  excluding alignment. Includes host eject awaiting CSW, failed automatic cleanup and failed Stop
  then successful Stop retry, pending/failed/queued I/O, remount and PHY-release retry,
  refused Stop while configured, suspend/unconfigure, stale tokens and ownership.
  Existing bounded-pump and delayed-packet tests also pass; no pump change.
- 31 production USB app/adapter scenarios pass in each of normal and UBSan runs
  (62 executions); Home remains gated while custody is retained, then works after
  release. Some cases intentionally terminate by controlled retained exit.
- Runtime CPU-resource port and binding tests pass. Four pinned HWCDC tests pass
  for stage-log and diagnostic settings: restored clock/reset/route/pads, RX/TX,
  absent-host repeat handback, retained failures and retry.

## Limits and pre-existing failures

The execution host is macOS arm64. Local invocation adapters supplied timeout,
Darwin dead stripping for unused TinyUSB optional hooks, and downgraded Clang-only
unused/missing-braces warnings. CDC testing used weak_import plus dynamic lookup
for Linux weak-reference semantics in a temporary SleepDiagnostics.cpp copy.
No production runtime/app source was edited. Full PHY dynamic-module lifecycle
runner cannot link its ELF-style fixture unchanged on Darwin; its port/binding
and separate pinned-HWCDC portions ran as reported above.

ASan executables timed out here, so no ASan pass is claimed. Full UBSan reports
an unaligned TinyUSB host load at tusb_common.h:264; rerun excludes alignment
explicitly. Linux fixed-address DWC2 test could not map 0x60080000 and was skipped.
These host checks are not SDMMC/controller/Windows hardware qualification.

The broader preparation integration harness fails its Home-release assertion
(usb_prepare_integration_test.c:59) with BOTH the unchanged pinned Reader and the
candidate. It does not link transport.c. Preserve this failed check as an
integration follow-up; do not label the complete preparation suite passed.
The individual production app/adapter and provider ownership suites passed.

## Integration requirements

1. Start from receipt 8e9e8eb7 on integrate/x4-reader-daily-078; preserve all Reader,
   Daily Paper, SD-app, launcher and panel 0.1.12 selections. Do not substitute an
   older firmware baseline or alter the historical .055 recovery ledger.
2. Select candidate Reader 4c2e2dbe for the MSC source/build input only. Keep
   TinyUSB 1eb6ce78 and pinned SDK/toolchain. A later explicit integration can
   build the changed MSC ELF with scripts/build_usb_device_msc.py, verify imports,
   relocation/admission and version 0.1.6, then regenerate paired hashes/custody.
   No new firmware or target ELF was built in this task.
3. Resolve/revalidate the pre-existing preparation harness failure and run the
   Linux DWC2/lifecycle and sanitizer checks in their supported environment.
4. Hardware qualification remains: Windows eject CSW/signaling, Stop retry,
   pending writes, SD remount, Home unlock and CDC re-enumeration. Do not equate
   suspend/unconfigure with eject, force writable remount under host custody, or
   report safe cleanup on a failed reset/configuration/lease release.

The source fix is ready for integration review. Windows not sending an observed
eject signal and residual slow directory reads remain separate unresolved issues.
No master merge, flash, firmware build or artifact replacement was performed.
