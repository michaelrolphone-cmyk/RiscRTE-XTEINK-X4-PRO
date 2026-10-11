# NOVA-7 Reader integration (0.1.76)

This source increment selects Reader 0.1.6 and scene-host 0.3.5 together over the
qualified 0.1.75 image. It is **not a claim of a completed 0.1.76 firmware build**.
The exact component commits are in `reader-nova7-076-sources.json`. The existing
native firmware, stable panel 0.1.12, boot/performance work and every unrelated
internal module remain the baseline selections.

## Assembly

Use clean checkouts of the pinned Productivity, System and Runtime commits.
Follow `Productivity/reader/NOVA7.md` to run engine/startup/GUI/FatFs tests and build
`ebook-reader/`. Build the System scene service with
`python System/scripts/build_scene_services.py --runtime Runtime --output scene`.
Retain the matching native `firmware.elf`, `firmware.bin`, `candidate.json`, full
0.1.75 image and its complete `build-custody.json` from the prior qualified bundle.
The shortened checked-in qualification summary is not the complete custody file.

From this repository's clean integration checkout:

```sh
python minimal/scripts/package_reader_refresh.py \
  --runtime /path/to/Runtime \
  --native /path/to/qualified-native \
  --scene /path/to/scene/scene-host \
  --reader /path/to/reader-build/ebook-reader \
  --tools /path/to/matching-tools \
  --baseline /path/to/X4-0.1.75-Reader-Panel-0.1.12-full-0x0.bin \
  --baseline-receipt /path/to/0.1.75/build-custody.json \
  --mkspiffs /path/to/mkspiffs \
  --output /path/to/new-0.1.76-output
```

The retained packager checks native bytes, baseline inventory, unchanged app
admission policy, Reader loader size, both new modules against the native
candidate, the complete internal cohort (normal and sanitized), deterministic
SPIFFS readback, and the paired image hash/CRC. It updates only the internal scene,
Reader manifest and cohort metadata; the app ELF remains on SD. Do not use the
older generic source lock to reconstruct a different native/panel baseline.

## Installation and behavior

The next firmware assembly must include scene-host 0.3.5 internally and Reader
0.1.6 in its admission manifest. Copy the matching ELF to
`Apps/ebook-reader/ebook_reader.elf` on the existing SD card. Keep existing fonts,
books and Reader state. **Copying the ELF alone onto firmware 0.1.75 is not enough**;
it lacks the new scene reading API. The Reader displays UPDATE FIRMWARE on that
older provider rather than calling beyond the old API table. A full 0x0 flash
replaces internal data; back up before using a subsequently assembled full image.

The library uses real EPUB/TXT/MD files, and + opens the SD browser rather than a
demo store. Remove Book hides a library entry without deleting the SD file.
Reading starts with hidden controls; edge taps change pages and center taps show
chrome. Font/layout preview, chapter navigation, bookmark removal, scrubber,
source-anchored released-swipe scrolling and monochrome inversion are native.
Completed pages remain static during idle checkpoints. Existing cache, SD recovery
and clean page-turn fixes are retained; the panel driver is not modified.

Run `python minimal/scripts/test_reader_nova7_recipe.py` to check the source recipe.
The component host tests, native framebuffer captures and Xtensa structural ELF
checks do not establish physical touch timing, panel ghosting, final cohort
admission or complete-image qualification. Those results are produced only by the
actual assembly and subsequent device tests, not this source pin record.
