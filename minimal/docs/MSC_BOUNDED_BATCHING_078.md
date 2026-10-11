# Bounded batching over combined .078 and cleanup .1.6

The requested implementation pairs shared MSC .1.7 with X4 SD .2.16. MSC forwards
at most eight whole sectors; SD export forwards those sectors in one native SDMMC
request. The existing generic block APIs and native eight-sector DMA buffer are
unchanged. Legacy GPIO export retains its sector loop. Every sector is still
charged to the shared operation budget before native IO, and failure retains the
export without falling back or retrying an uncertain write.

The production-path test moves 2 MiB each direction in 64-KiB host commands. The
same 4 MiB workload now uses 512 read plus 512 write SDMMC calls instead of 4096
plus 4096: an eightfold call-count reduction, not a measured speed increase.
Data endpoint submissions fall from 8192 to 1024; wire packets are still at most
64 bytes. Direct eight-sector export is one native call instead of eight.

Correctness cases include 1/2/7/8/9/15/17-sector commands, non-batch-aligned LBAs,
unaligned caller pointers, final card sector, invalid offsets/partial sectors and
out-of-range requests, short/failed data transfers, native read/write errors and
a write that commits one sector before failing. Uncertain IO retains media and
PHY custody with no replay. Queued reset cancels pending writes; host eject and
remount restore the original card hash and filesystem content.

The pump remains bounded at 32 passes/2 ms; it cannot preempt synchronous media
IO. A synthetic 10-ms batch test verifies only one admitted operation before
return, with a queued reset serviced on the next poll (the event hook aborts the
command immediately). Native timeout remains one second per request, no longer
multiplied across eight separately admitted SD commands. Hardware maximum latency
and actual Windows throughput still require measurement.

Existing v2 diagnostics provide buffered total/max IO times, command elapsed,
block counts, poll gaps, residue and errors after eject, before end() consumes the
session token. The test asserts post-eject access. No per-packet/per-sector serial
or SD logging is introduced. The connected app, active 1-ms polling and existing
bounded pumping are preserved.

Run minimal/scripts/test_usb_bulk_profile.py with the selected Reader, Runtime,
Drivers and TinyUSB checkouts, a new output, and optionally --ubsan. Physical USB
and SDMMC are simulated. UBSan excludes the known TinyUSB alignment issue; ASan
and Linux fixed-address controller qualification are not claimed on this host.

## Published source and qualified target binding

- Reader MSC source: `5fe5caa4cd7c8ab03d00e5e8e17cbac16053f743`, branch
  `perf/msc-bounded-block-batching-017`, includes cleanup .1.6.
- X4 SD source: `3c23b8bd2a1073bd1e3db48d6e9ae034613372c0`, branch
  `perf/x4-sd-bounded-batching-078`, based on combined .078 cleanup qualification.
- Runtime `7071f0c25e223f24670bed409a5f8b6f291c8042`, Drivers
  `ce31eefe0ebe62d373c9b0fb24d6f7059d2995d9`, TinyUSB
  `1eb6ce784ca9b8acbbe43dba9f1d9c26c2e80eb0`.
- Toolchain: GCC 8.4.0 esp-2021r2-patch5; Arduino framework
  `3.20017.241212+sha.dcc1105b` / IDF 4.4.7.

Compacted MSC .1.7 ELF is 34,992 bytes, SHA-256
`a8d5613723101f861f5f866ed5e33e1f2c1ec6d00668e799632461146688461c`.
Compacted SD .2.16 ELF is 55,228 bytes, SHA-256
`894a177889871d8430fe1122bb0655c8ae9488111544a673d872264428062bed`.
The ordinary packages, catalog, source hashes, target proofs and qualification
receipt are under `evidence/msc-batching-078/target/`. They are test packages
published on the branch, not installed or released firmware.

Both targets compile with the pinned toolchain. Compaction preserves allocated
sections, symbols and relocations; strict loader-map audits pass. Normal and UBSan
qualification each admit all 54 modules, reject wrong roles/unsafe operations and
missing imports for both changed providers, and pass three 38-ELF cohort checks:
original .078 to candidate, cleanup .1.6 to candidate, and candidate to candidate.
Every cohort check has zero hardware and storage calls. Only the two changed
ELF/manifest pairs differ from .078; all 16 SD apps, Reader, DailyPaper, launchers,
scene, native binary and panel .12 remain byte-identical.

Reproduce the target checkpoint without building firmware:

1. Run Reader `scripts/build_usb_device_msc.py` with pinned TinyUSB, framework,
   Xtensa compiler and a new output directory (Python requires pyelftools).
2. Run X4 `minimal/scripts/build_storage_fs.py --runtime RUNTIME --drivers DRIVERS
   --reference-reader READER --cc XTENSA_GCC --output SD_TARGET`.
3. Set `NATIVE_DRIVER_CC` to that compiler and run
   `minimal/scripts/qualify_msc_batching_078.py --baseline FINAL078
   --target MSC_TARGET --sd-target SD_TARGET --cleanup-store CLEANUP016_STORE
   --reader READER --runtime RUNTIME --tools WATCHAPPTOOLS --output NEW_RESULT`.
   FINAL078 is the exact combined image/SD archive used by the cleanup recipe;
   CLEANUP016_STORE is the verified staging store produced by that recipe.

No full firmware was emitted. Later integration must use both exact changed
packages, retain the combined payloads, assign a new product/cohort identity and
paired hashes, and read back the assembled store. Never replace an active or
retained provider. Actual Windows eject signaling, maximum UI latency and copy
throughput are still unverified on physical hardware; use the buffered final
checkpoint and host USB capture described in MSC_078_BULK_AND_EJECT_FINDINGS.md.
