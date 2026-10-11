# X4 0.1.73: first SD application cohort

The directly flashable BIN retains ten core applications and all 27 providers.
The separate SD bundle supplies fifteen optional application ELFs and Reader
fonts. Copy its `Apps/` and `fonts/` directories to the existing card root,
merging directories. Do not format the card or replace books, ROMs, models or
`System/State`. The full BIN is a 16 MiB image at offset zero and overwrites
internal settings/AppData. The SD card is independent of that image.

Core: Home, Springboard, Settings, Wi-Fi Settings, File Browser, USB SD Transfer,
OTA Update, App Store, Alarms and Battery. Optional apps include the current
Contexts, Spectrogram, Lists, Model Viewer, Hollow Trail and Reader. The stable
panel 0.1.12 executable is unchanged from 0.1.72. Apps request capabilities;
only platform selection chooses that driver and version.

Runtime 0.2.5 resolves each external executable through `storage.volume@1`.
It reads a fresh private snapshot, closes the source, then performs ordinary
ELF validation/relocation. No SD handle or raw source pointer remains in an app
mapping. A missing card does not prevent core boot. Absent/corrupt app files
return through the existing failure UI; uncertain close/release retains custody.
Model Viewer and Hollow Trail use explicitly registered destructive handoff,
as their recovered binaries do not carry resident foreground descriptors.

This first stage keeps app identities, grants and launcher entries in firmware.
Adding a new identity/grant still needs a platform policy update. Flash-only
App Store updates deliberately reject external apps; replace their SD files.
SD executables are never placed in the immutable internal image cache.

The follow-up SD-only patch supplies Hollow Trail 1.2.1 (black letterbox bands)
and Reader 0.1.1 (open its initial scene before querying page geometry).
Merge its `Apps/` tree over the existing card while these apps are closed.
No firmware or font replacement is needed. `sd-apps-073-hotfix.json` records
that first patch. Hollow Trail's full original story and aspect ratio are retained.

Reader **0.1.2** supersedes 0.1.1 after the device exposed a `loopTask` stack
overflow during book pagination. Resetting reading state in place reduces
`Engine::open`'s Xtensa frame from 5,744 to 128 bytes; bookmark edits retain
only one bookmark for rollback. Replace only `Apps/ebook-reader/ebook_reader.elf`
while Reader is closed. No firmware, font or JSON replacement is needed.
`sd-apps-073-reader-012.json` records the exact ELF, source, compiler stack
reports and native admission against 0.1.73. Real app-entry host tests now
render EPUB3, EPUB2, TXT and Markdown through the file-open handoff. Device
retesting remains pending for that stack correction.

Reader **0.1.3** supersedes 0.1.2 after fixing the storage port's cache-file open
mode. CrossPoint incrementally reads completed pages through its cache writer,
which requires read/write access. The port incorrectly requested write-only;
the host fixture failed to enforce that permission. Both are corrected, with
regressions through the actual production FatFs implementation. Tests cover
fresh, partial, completed and incomplete caches, reflow and bookmark retention.
`sd-apps-073-reader-013.json` records the replacement ELF and validation. Copy
only `Apps/ebook-reader/ebook_reader.elf`; leave saved Reader data in place.
Use Reader 0.1.4 and Hollow Trail 1.2.1 in subsequent assemblies; firmware static
version labels update with the next firmware build. Physical testing remains
pending; the panel selection is still 0.1.12.

Firmware **0.1.74** pairs Reader **0.1.4** with scene-host **0.3.3**. Library
launch now tolerates missing title/author fields and preserves Browse SD if the
derived index cannot be read. Resident battery/power checks restore the cached
page before rebuilding storage handles, avoiding the repeated opening screen.
Page changes request a full CLEAN/FIFO display refresh; routine restoration of
the same page retains the normal presentation path. The shared scene service
owns that intent and the panel remains byte-identical 0.1.12.

Flash `X4-0.1.74-Reader-Panel-0.1.12-full-0x0.bin` at `0x0`, then replace
`Apps/ebook-reader/ebook_reader.elf` on SD. The full flash overwrites internal
settings. Leave existing SD fonts, books, apps and `System/State` in place; no
apps JSON replacement is needed. The app-side fixes also run on 0.1.73, but
explicit clean page refresh requires the new firmware's scene service.
`reader-refresh-074-qualification.json` records target builds, real app-entry
and resident tests, clean page turns, scene lifecycle tests and full internal
cohort admission. Device testing remains pending.

Reproduce this focused firmware update with `scripts/package_reader_refresh.py`
using the exact qualified 0.1.73 BIN/native ELF, scene-host 0.3.3 and Reader 0.1.4
build directories. Supply the X4 ABI2 `mkspiffs` build with metadata length 4
for independent readback. The script preserves all native bytes and all
internal files except the scene service, its manifest, Reader metadata and
cohort identity, and regenerates the paired-bank record.

`sd-apps-073-qualification.json` records exact artifacts, source-tree publication
mappings, capacity and gate results. Tests cover normal/sanitized runtime
launch/return, image replacement, absent/busy/removed media, positive short
reads, corrupt/truncated images, allocation failure and checked-close retention.
All 52 app/provider images pass native admission; 37 internal images also pass
full cohort admission in both test modes without hardware/storage calls.
Reader engine, scene component and production SD filesystem tests pass.
Physical device testing remains pending.

Build with the recorded Runtime/System/Drivers/Productivity trees. Preserve
the qualified 0.1.72 store as baseline. Build the Home and Springboard using
`sd-app-catalog.json`, retaining the existing raster snapshots, boot animation,
resident, idle-sleep and settled-display flags. Build Reader with Productivity's
`scripts/build_reader.py`, shared scene services with System's
`scripts/build_scene_services.py`, and the SD provider with
`scripts/build_storage_fs.py`. The recovered Canvas binaries and their receipts
are carried forward unchanged. Stage an immutable single-job native Runtime
build with the existing policy24, requirement24, image cache, USB PHY,
retained-wake512 and failure-evidence options. `scripts/package_sd_apps.py`
accepts those components, the staged native candidate, its exact platform source,
the baseline BIN and the existing packaging tools. It admits both internal and
external images, checks the internal cohort, round-trips SPIFFS twice, verifies
the paired bank SHA/CRC, and emits the BIN plus deterministic SD ZIP.
