# Complete SD package for frozen X4 0.1.121

This packaging-only source checkpoint does not rebuild or modify firmware,
application images, drivers, fonts or device settings. It closes every external
image path in the published firmware's actual boot store.

Inputs are pinned by byte length and SHA-256 in `inputs.lock.json`:
- The official .87 complete overlay supplies unchanged applications and fonts.
- Five exact application images recovered from the delivered .103 package supply
  Timecard, Contexts, Lists, Hollow Trail and Reader. Their archive is retained
  as ordered 64 KiB parts; concatenation must match the pinned archive digest.
- The official .120 changed overlay supplies current changed applications.
- The official .121 factory image is read offline only. Its exact app manifests
  and 31 hash-named driver fallbacks supply the remaining card files.

The .111 historical app inventory supplies original hashes for unchanged plain
paths. Later GameBoy, BLE Buttons and OBDTest hashes are bound to the official
.120 package. Six content-addressed app paths and all driver paths additionally
carry their own expected image SHA-256 in the actual .121 boot record.

The output is a deterministic, uncompressed ZIP with exactly 77 files. Only the
49 boot-selected SD images, 18 exact app manifests, and ten bundled font/license
files are included. Older redundant image paths are not packaged. Installation
merges these files without deleting unrelated existing card content.

`test_complete_sd.py` checks closure, identity, reproducibility, manifests,
merge preservation and rejection of corrupt/missing/unsafe inputs.
`verify_complete_sd.py` reads native exports from the exact firmware BIN and
admits all 49 ELFs against pinned production Runtime code, including role,
unsafe-operation and per-import negative cases. No hardware is used.

The source-owned `complete-sd-121.yml` workflow downloads the exact public
inputs, packages twice, runs all tests and adds uniquely named assets to the
existing .121 release without replacing any existing asset. It checks every
published asset by downloading it again. A retry may reuse an identical asset
but cannot overwrite an asset whose bytes differ.

Use `COMPLETE-SD-INSTRUCTIONS.txt` for installation; release notes contain only
changes. The original firmware technical record is retained separately.
