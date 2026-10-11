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
