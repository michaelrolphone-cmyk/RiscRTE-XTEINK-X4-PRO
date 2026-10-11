# Files-only X4 0.1.92

This offline composition starts from the exact delivered X4 0.1.90 archives
identified by `minimal/recovery-090-qualified.json`. Its only store changes are:

- `file_browser.elf`: source-built Files 1.5.30
- `file_browser.json`: the same manifest authority with version 1.5.30
- `cohort.json`: product version 0.1.92 and the committed product recipe revision

`boot.json` stays byte-identical. Native Runtime
`3b90cd11cf0ff4e8116bb54d2d9eb9c7c67a148b`, all 26 application selections,
all 32 providers, and every other internal store file remain unchanged. In
particular, no keyboard provider or unpublished keyboard work is included.

Files is an internal-only selection: it has no `image_source`. All 81 files in
the delivered .90 SD archive, including all 46 selected SD images, remain
byte-identical. The recipe reads and audits that archive but emits no SD tree or
SD deliverable. Keep the existing verified .90 SD contents. An older or
incomplete SD installation does not satisfy this prerequisite.

## Exact inputs and source custody

- Product base: `c8004c5c8362b142ebb35a0e1c5d266532a11581`
- System: `1aaf53e23ca9651a5cf9d1debe44941c9d7d0e58`
- System tree: `df34bc79caeee0815230d2a35ec1995606ec66d6`
- Files: 1.5.30, 458,012 bytes
- Files ELF SHA-256:
  `38723f807d8fc5c61fcd393542041a3dff36a71e4b578ea5215dd7f683e1af42`
- Utilities SDK: `fc0bdbbbc600ce891e60c44d091fce0586ade7d8`
- Native firmware SHA-256:
  `4bcf29ab5077abe27a3aa8fd0745950de53846bf7c0a94e683fca2f2a0041b8f`

`minimal/files-092-inputs.json` pins the exact manifest, ELF and build-record
bytes. Composition requires clean committed System/Runtime/product sources,
checks all 312 recorded Files source hashes, and preserves the .90 build flags,
profile, requested capabilities, grant bindings and exact 16 resolved grants.
The .90 archive sizes/SHA-256 values are checked before ZIP parsing; traversal,
symlinks, duplicate members and checksum failures are rejected.

The deterministic ESP-IDF SPIFFS generator, independent read-only SPIFFS decoder
and bank-state helper are hash-pinned. Existing source tools are reused; shared
runtime implementations are not vendored into this repository.

## Reproduce the Files target

Use fresh output directories, the exact clean source checkouts above, and
Xtensa ESP32-S3 GCC 8.4.0 (`esp-2021r2-patch5`). This is the delivered .90 profile
with the published Files source update. Set each path for the local checkout.

```sh
export SYSTEM=/path/to/system-1aaf53e2
export RUNTIME=/path/to/runtime-3b90
export UTILITIES=/path/to/utilities-fc0bdbbb
export FILES=/path/to/new-files-092-target
export NATIVE_APP_CC=/path/to/xtensa-esp32s3-elf-gcc
export PLATFORMIO_SETTING_ENABLE_TELEMETRY=no
python3 "$SYSTEM/scripts/build_portable_file_browser.py" \
  --output-dir "$FILES" --display-rotation 90 --touch-rotation 0 \
  --storage-capability storage.volume --storage-instance 9 \
  --return-app springboard.elf --touch-scrolling --file-handlers \
  --alarm-client --navigation --time-profile x4-native-time \
  --native-time-runtime-repo "$RUNTIME" --tagged-alarm-utilities "$UTILITIES" \
  --ble-broadcast --resident-shell-client --resident-policy \
  --resident-runtime-sdk "$RUNTIME/sdk/app" --raster-snapshot --stage-logs \
  --home-app default.elf --peer-files --webdav-sharing \
  --sharing-export-instance 0 --sharing-tcp-instance 0 \
  --sharing-entropy-instance 0 --sharing-setup-instance 0
```

The pinned build-record hash is part of custody, not just an ELF hash. If a
future toolchain or input produces different bytes, investigate and qualify that
input separately instead of rewriting the lock to make the gate pass.

## Compose and independently verify

`BASELINE` is a directory containing the three exact delivered .90 ZIPs:
Recovery-Full-Image, Evidence-and-Components and SD-Overlay-Keep-Existing.
`TOOLS` contains the hash-pinned `scripts/current_bootfs.py`,
`scripts/read_only_spiffs.py` and `vendor/esp-idf-spiffs/spiffsgen.py`.
The verified assembly-tool checkout was Watch profile
`089868395268b696c05651c33816345bfe0425df`.

```sh
export BASELINE=/path/to/delivered-090-archives
export TOOLS=/path/to/watch-profile-tools
export OUTPUT=/path/to/new-files-092-composition
python3 minimal/test/files_092_composition_test.py
python3 minimal/test/shared_settings_composition_test.py
python3 minimal/scripts/compose_files_092.py \
  --baseline "$BASELINE" --files "$FILES" --system-source "$SYSTEM" \
  --runtime-source "$RUNTIME" --tools "$TOOLS" --output "$OUTPUT" \
  --product-revision "$(git rev-parse HEAD)"
python3 minimal/scripts/verify_files_092.py \
  --baseline "$BASELINE" --runtime-source "$RUNTIME" \
  --tools "$TOOLS" --output "$OUTPUT"
```

The raw output is `X4-0.1.92-FULL-INITIAL-ERASES-DATA.bin`, exactly 16,777,216
bytes, with no archive wrapper. The receipt and supporting files are in the same
output directory. The standalone verifier reads the written BIN and independently
decodes both full-image stores, confirms the three-path allowlist, verifies all
native/unrelated flash preservation ranges, checks bank-state CRC and firmware/
bootfs digests, and checks the staged evidence against those decoded bytes.
Only bank0 bootfs at `0x2f0000..0x800000` and initial bank-state at
`0xff2000..0xff4000` can change. This retains even erased/unallocated bytes in
every other flash range, rather than merely checking named components.

## Native admission

Run the existing strict installed-catalog gate with the exact delivered native
ELF/BIN pair and the existing .90 SD tree. Its .92 extension checks the complete
store/SD inventories, unchanged native/boot authority and the three-path
allowlist before admitting the same 46 selected SD images. The historical .90
admission path remains supported.

```sh
python3 minimal/scripts/qualify_installed_catalog.py \
  --runtime "$RUNTIME" --tools "$TOOLS" \
  --native-bin /path/to/exact-090-native/firmware.bin \
  --native-elf /path/to/exact-090-native/firmware.elf \
  --store "$OUTPUT/store" --output /path/to/new-files-092-admission \
  --provider-capacity 40 --shared-files \
  --sd /path/to/exact-090-sd/SD \
  --composition-receipt "$OUTPUT/receipts/files-composition.json"
```

Strict ELF/import and cohort admission do not execute providers or applications.
Hardware testing remains separate. The recipe itself does not publish, upload,
flash a device or claim those later qualification steps passed.

## Data-loss and persistence limits

This is a full initial image. Flashing it at offset zero erases internal settings,
saved Wi-Fi networks and native app data. It is not a preserving update.
The experimental shared-settings opt-in remains disabled, exactly as in .90.
No new SD settings backup or recovery mechanism is introduced by this Files-only
increment. Keeping the SD card does not recover native-only data erased by full
flashing. No hardware or device operation was used to create this composition.
