# Cumulative X4 0.1.108: RF modal policy 0.3.5

The input is the preserved .107 clock image, SHA-256
`ccb38661dc5535d6447275d5815ad9f5744133f155709c7c71a32a5b0806641d`.
The historical RF selection is source/profile evidence only. Its old full-image
baseline and old Runtime are never composed into this image.

## Exact RF component

Utilities `52157660ec573cf4639ffe3eefcad5b7b3115c4e` and System
`fd4b1e52fe2a49c3c4c22f9ccd4c98a91f88afa0` reproduce the qualified X4 RF
ELF exactly: `f670dc7ec2194a80a75057d818f87314d76721f3b0e811af4994568ef0618ac1`,
284800 bytes. Manifest hash is `c280c4c111c9ea7899b33dfa6956fd94b25ecffb860c8e8b3b20bd1d9bc477da`.
The sole selected feature addition is PORTABLE_TEXT_INPUT_POLICY.
Continuous capture, model/training work, original fonts, storage contracts,
resident policy and X4 portrait selection retain the qualified source profile.
No Watch-only app binary is used.

`build_rf.py` verifies every qualified target dependency hash, reconstructs each
SDK header from an exact matching source file, and verifies the generated catalog.
The catalog is reproduced by System's `catalog_source` from
`examples/x4-resident-cohort-catalog.json` (SHA-256 of generated C: 6ea2e4d1ff001d07f1a92b89dd24191ac8c5d806c4b3d857516bf81d05939e54).
Build SDK commit `1c1ed8661ea30d47e7e9707c41d492ce3a2b4d70` supplies historical
header identities only. Deployed native firmware stays byte-identical at
`a91edf3fada6a559ec107186dd163d0c8da10d29`; the actual native BIN export table
is re-read for admission. Compaction preserves allocated sections, symbols and
relocations, checked by the existing loader-metadata-v3 helper retained from
shared RiscRTE-Watch build tooling commit 362537417c4f37bbb240879d5ba756686511fec1.

## Cumulative preservation and SD delta

Only `waterfall.json`, `boot.json`, and `cohort.json` change in the 107-file store.
The only boot change is RF's SD image path; all grants and other rows are equal.
All 43 internal ELFs, including .107 Home 0.4.18, are unchanged, as are native
firmware, flash settings regions, OBDTest registration, Files and text host.
Product version advances to 0.1.108. Baseline SPIFFS is reproduced before packing.

The SD ZIP adds exactly two files below
`Apps/waterfall/image-f670dc7ec2194a80a75057d818f87314d76721f3b0e811af4994568ef0618ac1/`:
`waterfall.elf` and `manifest.json`. Merge these into the existing card; retain
all original files, including `Apps/waterfall/waterfall.elf` and its old manifest.
No existing SD path is rewritten or deleted. A complete physical-card inventory
was not available and is not claimed to have been audited.

## Verification

The target must equal the independently qualified X4 ELF and manifest on both
local and Linux builds. `verify.py` admits 43 internal modules plus the new SD RF
module with the production strict loader and role/import/unsafe/missing-import
negative checks; the .107-to-.108 complete internal store transition passes
normally and under UBSan, with zero hardware and storage calls.

`test_modal.py` runs the pinned Utilities real-app/adapter/text-host/scene-host
fixture for X4 with deployed native SDK a91edf3. It replaces only the preliminary
font-generation step with the exact formerly generated glyph bytes expected by
the original fixture. The original hash assertion and all lifecycle assertions
remain active. This avoids Pillow/FreeType wheel drift, which otherwise failed
before any scenario. The compressed glyph fixture has SIL font licenses beside
it and expands to SHA-256 2d7501e42d6223ebbc191817715431182c435fea944a1a02166a0748a577eaf1.
The scenarios cover stopped-radio Done/Cancel, active capture/progress, unavailable
checkpoints, continuous resident policy, and terminal retained resume, normally
and with ASan/UBSan. CI receipts record their final outcomes.

## Reproduction and hold

The workflow pins sources and compiler and runs target/lifecycle qualification.
For cumulative assembly, run `assemble.py --baseline <107.bin> --rf <target-dir>
--runtime <native-a91-checkout> --spiffsgen ../recovery-107/vendor/esp-idf-spiffs/spiffsgen.py
--product-commit 55d5dd672e6568376fcdd39df074612612f89c71 --output <new-output>`.
The original selection and qualified target receipts are retained as evidence;
do not execute their historical whole-image composer.

Delivery remains held until 2026-10-13 23:30 UTC. No merge, release or flash is
performed. A full 16 MiB BIN overwrites internal user data when flashed; unchanged
baseline settings regions do not preserve the live device's current settings.
Physical RF, input, power/sleep and RTC/Home regression checks remain outstanding.
Points and Scanner source reconciliation is outside this completed RF delta.
