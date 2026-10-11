# Reader chapter links: X4 0.1.77

Pair Reader 0.1.8 with scene-host 0.3.6. `reader-links-077-sources.json`
selects the exact CI-built components and the original delivered X4 0.1.76 BIN.
It preserves native Runtime 0.2.5, panel 0.1.12, and all unrelated applications
and providers. Component compilation uses a compatible SDK; assembly validation
uses the actual native 0.2.5 source and resolver tables observed in the BIN.

## Assembly

With the pinned runtime/tool sources and the unpacked Reader/scene CI artifacts:

```sh
python minimal/scripts/package_reader_bin_overlay.py --version 0.1.77 \
  --source-revision "$(git rev-parse HEAD)" \
  --baseline /path/to/X4-0.1.76-Reader-Panel-0.1.12-full-0x0.bin \
  --runtime /path/to/Runtime075 --tools /path/to/Tools \
  --mkspiffs /path/to/Mkspiffs/mkspiffs \
  --reader /path/to/reader/build/target/ebook-reader \
  --scene /path/to/scene/reader-scene/scene-host \
  --output /path/to/new-0.1.77-output
```

The original 0.1.76 recipe remains available with `--version 0.1.76`.
The assembler retains strict application/provider ELF roles and all missing-import
checks, both 37-module cohort transitions normally and under ASan/UBSan, baseline
byte reproduction, deterministic store generation, independent C SPIFFS readback,
paired-bank SHA/CRC and unchanged-byte ranges. It does not execute target
instructions or use a synthesized native ELF. Full results are in build-custody.json.

## Install

Use the full 16 MiB image at offset 0x0 and replace the SD app at
`Apps/ebook-reader/ebook_reader.elf` with the paired Reader 0.1.8. **Both updates are
needed for inline-link tapping.** Keep SD books, fonts, state and other apps.
A full flash overwrites internal NVS, settings, Bluetooth bonds and AppData;
back up those before flashing. It does not write the SD card.

Tap an internal EPUB link to navigate to its chapter or anchor. Back returns to
the originating reading position; the bounded 16-entry history belongs to the
current app invocation. Contents rows continue to navigate independently.
Relative paths, percent-encoded names and incremental chapter anchors are covered
by engine and actual-app touch tests. External web URLs and unsupported targets
report errors rather than silently pretending to navigate. The Reader 0.1.7 warm
cache/SD performance changes, clean page refresh and static-page behavior remain.

CI and host assembly checks do not establish physical touch accuracy or hardware
page-turn timing. Hardware testing remains pending.
