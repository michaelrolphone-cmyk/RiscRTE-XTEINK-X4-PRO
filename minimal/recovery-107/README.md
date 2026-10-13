# X4 0.1.107 cumulative Clock repair

This composition starts with the exact delivered .106 full BIN, SHA-256
`524a5fc3aa4bba634a373a82bed384969104d26778d192e8e8feca7b9b1407d2`.
It advances Home from delivered 0.4.17 to 0.4.18 and product 0.1.106 to 0.1.107.
System PR111 supplies bounded foreground RTC reconciliation and retains PR110's
Home startup/alarm-loading safeguards. The lost d3eb532 candidate is not claimed
as recovered source.

Only `default.elf`, `default.json`, and `cohort.json` change in the 107-file store.
All 42 other internal ELFs, native Runtime, boot registration, capability grants,
OBD/OBDTest side-by-side entries, drivers, and settings flash regions are unchanged.
The identical capability requirements retain the delivered manifest ordering.
The SPIFFS generator first reproduces the complete .106 store byte-for-byte,
then packs the new store twice identically. There are 116 spare blocks.
The bank-0 record is regenerated and checked against unchanged native and new store.
No SD overlay is required relative to the working .106 installation; keep its SD files.

## Source and target evidence

`evidence/source-pins.json` records immutable source pins and successful comparison
of every recovered Home feature define, desk SDK header, tagged-alarm SDK input,
and sleep-hook hash. `evidence/home-build-evidence.json` records the clean System
source, compiler, target hash and imports. The full recovered feature profile is
built twice in the pinned Linux target workflow; both ELF and manifest match.
The compiler is Espressif 8.4.0 / esp-2021r2-patch5. A macOS linker assertion and
local Docker startup stall were bypassed using GitHub Actions without changing flags.

The .105 source fixtures and native resolver proof are retained under `fixtures/`.
`verify.py` re-reads the actual native BIN export table and compares it with that
proof, then runs production strict ELF admission and complete-store transition
from .106 to .107. No target machine code or hardware is executed.

## Reproduction

Use exact dependency pins from `evidence/source-pins.json`; the workflow gives the
complete target checkout and build commands. Reader driver SDK is composed with
this repository's `minimal/interfaces`, preserving delivered header hashes.
The build recipe needs the pinned Utilities history for its canonical alarm SDK.

After obtaining the exact .106 input and the target workflow artifact:

```sh
python minimal/recovery-107/assemble.py --baseline /path/to/106.bin --home /path/to/target/home --runtime /path/to/RiscRTE --spiffsgen minimal/recovery-107/vendor/esp-idf-spiffs/spiffsgen.py --system-commit 3f7474bbbdaacb7fb196a8c6b74a23017eff2772 --output /path/to/output
python minimal/recovery-107/verify.py --runtime /path/to/RiscRTE --x4 . --output /path/to/output --fixtures minimal/recovery-107/fixtures --native-proof minimal/recovery-107/fixtures/native-resolver-105.json --baseline-store /path/to/extracted-106-store --mode normal
```

The host verifier needs pyelftools 0.32 and a C/C++ compiler. Use `--mode undefined`
for UBSan or `--mode asan` for ASan/UBSan on a supporting host. The only Darwin
warning exception is a pre-existing unused Runtime host-profile counter; production
source is untouched. SPIFFS generator is hash-pinned, with its Apache-2.0 license.

## Delivery and hardware

User delivery is held until **2026-10-13 23:30 UTC**. This is not permission to merge,
release or flash. The full 16 MiB image flashes at offset 0 and overwrites internal
user data; unchanged baseline settings regions do not imply preservation of data
currently on a physical device. Back up device data before any separately authorized flash.

Physical qualification remains: compare all six faces against RTC Settings over
frequent refreshes and overnight operation; exercise cold boot, manual sleep,
light/deep sleep, timer wake and GPIO foreground wake; check Home startup, alarm
loading, original OBD and OBDTest, installed apps and SD settings. Timer-only deep
wake keeps native authority; reconciliation occurs after foreground promotion and
does not recalibrate the hardware oscillator.
