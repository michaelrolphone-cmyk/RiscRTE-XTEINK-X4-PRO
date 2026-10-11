# X4 0.1.78 — Reader links and Daily Paper

This increment combines PR29 at `2f33a6561e2a0bd7275e6a4fc58c4cc4f3aa5e6d`
and PR30 at `cff7d1e563cec5d880d5fbbfa0ca5bfec3081d0a`. Both heads were
checked against GitHub before integration. The highest remote product version
was 0.1.77; this combined build uses 0.1.78.

The exact delivered Daily Paper image supplies Home 0.4.8, Springboard 1.7.31,
Daily Paper registration and HTTP provider. The paired Reader delivery supplies
Reader 0.1.8 and internal Scene 0.3.6. Runtime 0.2.5, panel
`x4pro-uc8279-fast` 0.1.12 and all other Daily Paper internal files except the Hollow Trail version manifest remain
byte-identical. Touch/UI decoupling is retained without reimplementation.
There are 26 registered apps, 28 providers and 24 launcher entries.

## Installation

Use `X4-0.1.78-Reader-Daily-Paper-Panel-0.1.12-full-0x0.bin` at **0x0**.
This is a full 16 MiB image. It overwrites internal NVS, settings, Bluetooth
bonds and AppData; back up needed internal data before flashing.
There is no preserving OTA package or claim of preserving OTA support.

Merge `Apps/` and `fonts/` from `X4-0.1.78-Reader-Daily-Paper-SD.zip` into the existing SD
root. It contains all 16 SD apps and matching manifests, including Reader **0.1.8**,
Daily Paper 0.1.0 and the previously delivered Hollow Trail 1.2.1 correction,
plus Reader fonts and licenses. Preserve other applications, books, fonts and state. Both firmware
and SD updates are required for chapter links. Configure Wi-Fi and date/time
after flashing as needed. Daily Paper downloads the latest edition to
`/Books/Daily Digest/YYYY-MM-DD.epub` and hands it to Reader.

## Reproduction and validation

`minimal/scripts/package_reader_daily.py --help` lists inputs. The script
requires exact hashes of the delivered .76 baseline, both .77 images and both
SD packages. It refuses modified inputs or an uncommitted composition. See
`reader-daily-078-sources.json` for source pins. The Runtime and Tools checkouts
must be at their pinned versions; mkspiffs 0.2.3 must be built with
`SPIFFS_OBJ_META_LEN=4`. Use pyelftools 0.32. The existing migration preparation
workflow remains unchanged; this recipe composes already qualified binaries
and does not rebuild or vendor the native runtime.

The recipe checks all 54 supplied ELF modules against production admission,
including roles, unsafe operations, and every missing import in seven affected
modules. It tests four installed cohorts, the Daily-to-combined transition,
and expected refusal of .76/Reader-to-combined namespace expansion, normally
and under the explicitly selected sanitizer mode. The default is ASan/UBSan;
`--sanitizers undefined` records UBSan-only verification when host ASan cannot
initialize. An unavailable ASan run must be reported as a limitation. Passing the Daily transition is an admission check only,
not an OTA delivery qualification. Independent C SPIFFS unpacking checks all
four stores. Partition MD5, bootloader/native ESP checksums and appended SHA,
paired-bank SHA/CRC, exact unchanged ranges, deterministic packing and final
BIN/SD readback are required.

Host compilation supports Linux and macOS. macOS omits Linux-only linker flags
and suppresses Clang's unused-field/unused-variable diagnostics for unchanged
production code. Sanitizers and admission assertions remain enabled.

The component binaries are reused, not recompiled. Prior target builds and
app behavior tests are distinguished from this increment's fresh integration
qualification. Hardware behavior, download operation and page-turn timing on
the combined build remain untested. No device flash, main-branch merge or
release is performed by this work.
