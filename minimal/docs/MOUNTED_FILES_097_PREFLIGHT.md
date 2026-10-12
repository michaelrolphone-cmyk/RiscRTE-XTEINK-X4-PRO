# X4 .97 mounted Files: local preparation only

This composition prepares Files 1.5.31 over delivered X4 .96. Combined System
publication is blocked. The recipe requires `--preflight-only`, emits an image
named `LOCAL-PREFLIGHT-NOT-FOR-DELIVERY`, and records the pending publication and
required final rebuild. No image, source or SD archive is published by it.

## Source and baseline custody

- X4 .96 baseline: `075f7a70d186fcbc5e93e0a8c10b4a16bd23d02c`.
- Delivered .96 BIN: `f643f9bba2f72c29e6cc3ea0f27aaf811d82ac94f05bf84db7d4f2478718783c`.
- Runtime .2.24: `6377d498a47b59dac8ad85d930983fffc6c8baa5`, unchanged.
- Local System qualification: `d793eb6ee54ed293fd4d19b452dd66202082c448`.
- Exact Files build: `cbf8c5d50b70068db8bd47f331ac7167c79c6ed0`.
- Files ELF: `65351dea1e1310f97ccfdd0e4a72782e5f69ef8cd34262453dde4d02d3d00011`, 483,608 bytes.

`files-mounted-097-inputs.json` binds all five .96 receipts, the native BIN/ELF,
the delivered manifest overlay, both local System trees and all Files artifacts.
The recipe verifies all 312 compiled source hashes against both the clean
qualification checkout and exact build commit. Profile switches, storage
selection, protected settings and all sixteen authority grants remain unchanged.

Only internal `file_browser.elf`, `file_browser.json` and `cohort.json` change.
One hundred other store files and all eighty-one .96 SD files remain identical.
All thirteen .96 installed foreground lifecycle declarations remain. Home .4.13,
the native firmware, launch behavior, providers, boot authority and .95 physical
packing order remain unchanged. This is a Files executable update; it is not
correctly described as packaging-only. The larger Files image consumes seven
additional 4096-byte SPIFFS blocks, leaving 225 free.

The SD tree staged beside the local preflight is for admission. No new SD
archive is created. Its baseline includes the delivered .96 thirteen-manifest
overlay; an older SD tree cannot be substituted.

## Reproduction

Set `PYTHONPATH` to a local pyelftools installation. Run
`minimal/test/mounted_files_097_test.py` with `--baseline`, `--files`,
`--system-source`, `--runtime-source` and `--tools`. Its source-bound positive
checks and 207 rejection probes test changed grants/profile, unrelated store/SD
bytes, cohort identity, artifact locks and forbidden flash-range mutations.

Commit the recipe locally, then run `minimal/scripts/compose_mounted_files_097.py`
with those arguments, the clean local `--product-revision`, `--preflight-only`
and a new `--output`. Use `verify_mounted_files_097.py` to independently decode
the full image and verify preserved ranges and bank-state CRC/digests.

Run `qualify_installed_catalog.py` with `--provider-capacity 40 --shared-files`,
the exact matching native BIN/ELF, generated store/SD and
`receipts/mounted-files-composition.json`. This performs strict import/role
admission of all 42 internal and 46 selected SD ELFs plus four namespace
rejection probes. It does not execute target applications or providers.

Before any delivery, resolve System publication authorization, publish through
the authorized path, update the recipe to the final published System SHA,
rebuild Files from that clean source, bind new receipts, rerun full qualification,
and publish the exact product source. Do not reuse this test image as a release.
No hardware, Mac, local desktop, Codex or physical-device access is used.

## Completed local preflight

The exact clean recipe source tested is
`a327b4e320f40ece1c1b3852e55b21882f04ca16`. An evidence-only checkpoint may follow
it without changing the tested recipe or retroactively relabelling its image.
All 207 negative probes and independent 16 MiB decode/preservation checks pass.
Exact-native strict admission passes for 42 internal and 46 selected SD ELFs;
all four namespace mutations are rejected. Graph admission makes zero hardware
or storage calls. This admission uses UBSan; it does not execute target code.

Seven SPIFFS read plans pass normally and under ASan/UBSan, with every read byte
compared against the expected store. Metadata name reads remain 193, healthy-SD
first-frame name reads 205, timer fallback 225 and full fallback 320. Cold-SD
lookup reads increase from 1,687 to 1,688 as the larger Files ELF shifts later
physical pages. Random all-file reads change from 74,444 to 74,489 and full
payload reads increase with Files size. These are host counts, not hardware
latency measurements. The existing packed-index alignment instrumentation
exception and ptrace leak-detector limitation are retained and recorded.

The local test image SHA256 is
`4d6787ab710d5d5d7ba96f839f7751070c97c0bcb30923f0892ec1391ff24c57`.
It is not published, delivered or hardware-qualified. Exact commands, source
pins, baseline receipts, validators and output digests are recorded under
`evidence/mounted-files-097`. No forbidden publication was retried.

### Delivered Files lineage

Direct comparison confirms .96 still contains exactly the .92 Files 1.5.30 ELF
and manifest. Its pinned build receipt identifies System source
`1aaf53e23ca9651a5cf9d1debe44941c9d7d0e58`, which is an ancestor of mounted
`cbf8c5d50b70068db8bd47f331ac7167c79c6ed0`. No later Files-specific executable
fix was introduced in delivered .96. The exact ELF, manifest and original build
receipt digests, ancestor check and changed compiled-source paths are retained
in `baseline-files-custody.json`.
