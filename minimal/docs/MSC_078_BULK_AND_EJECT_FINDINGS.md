# Combined .078: bulk-transfer and Windows-eject follow-up

Cleanup target qualification is in `MSC_CLEANUP_078_INTEGRATION.md`. This follow-up
adds source-bound tests and analysis, not a production performance change. No
full firmware was built or flashed. No physical transfer rate is asserted.

## Actual selected path

MSC is Reader `4c2e2dbe3bf587b51873c65a1a1c3faf4035e884` (.1.6), over the exact
.078 baseline receipt `8e9e8eb7a2b1f7f860777d0d0e8a89dd2822af87`. SD is X4
.2.15 and the native SDMMC backend is Runtime
`7071f0c25e223f24670bed409a5f8b6f291c8042`. Shared StorageFatFs is Drivers
`ce31eefe0ebe62d373c9b0fb24d6f7059d2995d9`, as in the .073/.078 source binding;
the historical Reader lock alone does not supply the latest filesystem extension
functions. TinyUSB is `1eb6ce784ca9b8acbbe43dba9f1d9c26c2e80eb0` plus the existing
Reader staging patches. Per-file hashes and compiler commands accompany the test.

The selected SD path is hardware SDMMC, one-bit, capped at 20 MHz, with actual
negotiated clock exposed by the native backend. Legacy GPIO bit banging is not
the selected production transport. `NativeSdmmc.h` has an eight-sector owned DMA
buffer and one native read/write transaction per generic call. The generic
storage export and SDMMC APIs already allow up to eight sectors.

MSC `tusb_config.h` nevertheless sets a 512-byte class buffer, and `driver.c`
READ10/WRITE10 callbacks require exactly 512 bytes and request one export block.
X4 `Export.h` additionally splits any multi-block export into individual
`read_sector`/`write_sector` calls. Thus simply enlarging the TinyUSB buffer is
insufficient: current callbacks would reject it, and merely changing callbacks
would still leave the SD-side split.

## Reproduced boundary counts

`test_usb_bulk_profile.py` compiles the actual selected MSC, patched TinyUSB,
X4 SD driver, and shared FatFs. Only USB DCD, physical SDMMC, GPIO and clock are
simulated. The existing native-card fixture supplies the media. Its historical
protocol-header include is redirected to the selected shared helper to avoid
compiling two copies. This adapter does not alter production transport code.

Sixty-four 64-KiB READ10/WRITE10 commands move 2 MiB in each direction:

| Boundary | Reads | Writes |
| --- | ---: | ---: |
| Export calls | 4,096 | 4,096 |
| Export blocks per call | 1 | 1 |
| Native SDMMC calls | 4,096 | 4,096 |

There are 8,192 class data transfers. These are 512-byte endpoint submissions,
not USB wire packets; full-speed bulk packets are at most 64 bytes. A separate
eight-block export produces eight native calls. Read data, written pattern,
restored whole-card hash, frozen local filesystem admission, genuine host-eject
CSW completion, PHY release and filesystem remount all pass. Counts are kept in
RAM and printed only after teardown, so no per-block synchronous logging is added.
Normal and UBSan runs pass. UBSan alignment checks are excluded for the existing
TinyUSB unaligned wire-header access; this is not an unrestricted sanitizer pass.

Reproduce with Python supporting the existing SDK preparation scripts:

```sh
python minimal/scripts/test_usb_bulk_profile.py \
  --reader /absolute/Reader --runtime /absolute/Runtime \
  --drivers /absolute/RiscRTE-Drivers --tinyusb /absolute/TinyUSB \
  --output /absolute/new-output
# Repeat with a fresh output and --ubsan.
```

## What these counts establish

The software performs avoidable transaction setup per sector. A bounded eight-
sector path could reduce native transactions eightfold for aligned eight-sector
chunks; that is a call-count prediction, not an eightfold speed claim. A focused
future implementation must change both shared MSC callback/buffer handling and
X4 export forwarding, preserve the generic block API, validate partial/short
final transfers and range overflow, and retain custody after every uncertain
write. It also needs reset/eject/pending-transfer tests with the larger buffer.
No speculative batching change is included in the qualified cleanup package.

ESP32-S3 USB is full speed, 12 Mbit/s. Espressif documents the ideal bulk payload
limit as 19 x 64 bytes/ms (1,216,000 bytes/s), before real software/card overhead:
https://docs.espressif.com/projects/esp-iot-solution/en/latest/usb/usb_overview/usb_otg.html
A faster USB card reader is therefore not a rate-equivalent baseline. This ceiling
does not explain arbitrarily slow transfers or the reported regressions.

There is no forced native sleep per USB packet or per sector. Native SD operations
are synchronous; the SD cooperation policy can yield after its existing time
budget. The existing bounded active pump and 1-ms active UI cadence remain in
place. MSC does not sync the card after every sector; it syncs explicitly at
cache-sync/eject. Directory traversal and host filesystem metadata patterns can
add small random requests, but this profile is bulk traffic and still exposes
the sector split. Existing command/IO counters and buffered diagnostics should
be collected before claiming which cost dominates elapsed copy time.

## Windows safe-removal signaling remains unproven

No actual Windows USB capture for the reported failure was available in the
inspected evidence. The source and host tests establish the following behavior:

| Host/device event | Meaning and cleanup behavior |
| --- | --- |
| START STOP UNIT, load/eject=1, start=0, power=0 | Successful card sync sets eject requested; successful CSW completion then sets eject complete and permits cleanup. |
| START STOP UNIT without load/eject | Does not establish safe host removal. |
| SYNCHRONIZE CACHE | Flushes; does not relinquish host ownership. |
| USB suspend, reset, or unconfigure | Recorded; does not establish safe eject or authorize writable local remount. |
| Physical unplug event | Aborts command and enters the disconnect cleanup path; transport and ownership checks still apply. |
| Transport restore failure | Retains SD/PHY ownership and locks Home; Stop can retry cleanup. |

The fixed RO-register comparison explains false transport retention *after*
cleanup is attempted. It cannot prove Windows sent the required eject command or
that its CSW completed. Do not reinterpret suspension as safe eject to hide this
remaining uncertainty.

A hardware qualification should retain the Windows USBPcap/Wireshark trace and
post-session buffered device diagnostics for: sequential large-file read/write,
Windows safe removal, Stop retry after a retained failure, reset during pending
IO, reconnect/remount, and CDC restoration. Correlate CBW opcode/LBA/block count,
CSW status and timestamps with start_stop_flags, eject_requested/eject_complete,
reset/unconfigure/suspend/resume counts, IO milliseconds and transport timeouts.
Measure bytes/time at the host, command idle gaps and SD IO time separately.
Do not enable synchronous serial or SD logging while exported, and do not remount
writable media until ownership release is proven. Physical results are still
required to close the Windows signaling and real-throughput questions.
