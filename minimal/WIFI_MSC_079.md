# X4 0.1.79 — Wi-Fi resident scan and MSC cleanup

This test increment uses the exact delivered combined 0.1.78 full image
SHA-256 `1d24836ca58c1f6ca841d3d9a41c38a3ad459e95746760de363a32e5ba04e7b5`.
Live remote product versions were checked before reservation; 0.1.79 was free.

Only these completed fixes are selected:

- Wi-Fi 1.1.25: System `f5673befd745a744872e4802332e647d64577a5c`;
  X4 evidence `6edc3f7b4db354141075d495956f92a37eb94738`. The resident POLL
  checkpoint stays BUSY locally while async radio ownership remains, keeping
  input/render/cancellation scheduling alive without crossing the exit barrier.
- MSC 0.1.6: T5S3-Reader `4c2e2dbe3bf587b51873c65a1a1c3faf4035e884`;
  X4 evidence head `563c0453e50baf1819149d65e82f27d64fdcd14a`, superseding
  `b09e5a4`. Shutdown verification masks only writable TEST_CONF bits.

`package_wifi_msc_079.py` verifies source-file hashes, component target receipts,
the MSC package/loader map, and exact executable hashes. It replaces only
`wifi_settings.elf`, `wifi_settings.json`, `usb-msc/driver.elf`,
`usb-msc/manifest.json` and `cohort.json`. All 90 other internal files, native
Runtime 0.2.5, and x4pro-uc8279-fast panel 0.1.12 remain byte-identical.
This preserves Reader 0.1.8, Scene 0.3.6, Daily Paper 0.1.0, Home 0.4.8,
Springboard 1.7.31, Hollow Trail 1.2.1 and the complete 16-app SD split.
USB throughput batching and dynamic package discovery are excluded.

## Install and SD compatibility

Flash `X4-0.1.79-WiFi-MSC-Panel-0.1.12-full-0x0.bin` at **0x0**.
It is a full 16 MiB image and overwrites internal settings, NVS, bonds and
AppData. Back up anything needed. No preserving OTA support is claimed.

The matching SD package is intentionally the unchanged
`X4-0.1.78-Reader-Daily-Paper-SD.zip`, SHA-256
`b7e504f16d717df839f974f0dde6e5f33cf9ff303e49fbb7936784447298d2e8`.
An already complete .78 card needs no SD changes. Otherwise merge its `Apps/`
and `fonts/` folders into the card root, replacing matching files while apps are
closed. Preserve other apps, books, ROMs, models, bookmarks and System/State.
Both repaired components are internal; an SD-only replacement cannot select them.

## Checks and limits

Reproduce with `minimal/scripts/package_wifi_msc_079.py --help` using the pinned
Runtime, verification tools, source checkouts and component outputs. The recipe
checks 54 actual modules against deployed production ELF admission, incorrect
roles and unsafe-operation rejection, all missing imports of the two changed
modules, and three installed/transition cohort cases without hardware/storage
calls. It runs normal and explicit sanitizer modes (UBSan by default), then
independent C SPIFFS readbacks, deterministic packing, partition MD5,
bootloader/native ESP integrity, paired-bank integrity and final BIN readback.

Prior target-build and regression receipts are carried forward as component
evidence; this integration reuses those exact binaries. New ASan or Linux
fixed-address DWC2 execution is not claimed. Physical Wi-Fi scanning/recovery,
Windows safe removal, retained Stop retry, pending transfers, SD remount and
CDC re-enumeration still need device testing. No hardware flash, main merge
or release is performed by this assembly.
