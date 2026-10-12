# X4 .97: published-source mounted Files composition

This supersedes the publication block described in
`MOUNTED_FILES_097_PREFLIGHT.md`. The qualified preflight is retained as historical
evidence; its locally named test image is not the release image.

## Published source and rebuild

Files 1.5.31 is rebuilt from clean published System source
`0accd8905b5a64bf5e9269fe92a6e47c9fd1cc90`, tree
`eb8ddcc0c17c915d409593d54b3304a4ca90f87b`, on
`feat/files-mounted-peer-browser`. This tree equals qualified local `d793eb6`.
The final ELF and manifest are byte-identical to the qualified `cbf8c5d` build;
only the build receipt's repository commit changes. The ELF SHA256 remains
`65351dea1e1310f97ccfdd0e4a72782e5f69ef8cd34262453dde4d02d3d00011`.

`files-mounted-097-final-inputs.json` pins the published System identity and
rebuild, all .96 baseline receipts, native identities and unchanged Files
profile. All 312 compiled source hashes are checked against the published commit.
Sixteen existing capability grants remain; there is no authority expansion.

## Preserved .96 composition

The baseline is delivered X4 .96 source
`075f7a70d186fcbc5e93e0a8c10b4a16bd23d02c` and raw image
`f643f9bba2f72c29e6cc3ea0f27aaf811d82ac94f05bf84db7d4f2478718783c`.
Only internal Files ELF/manifest and the product cohort identity change.
All 100 unrelated store files, all 81 SD files, all .96 lifecycle declarations,
Home .4.13, Runtime .2.24, providers, grants and native flash ranges remain
byte-identical. No later Files executable fix exists in .96 beyond the .92
Files 1.5.30 source `1aaf53e`, which is an ancestor of the mounted build.

Boot packing order is preserved. The larger Files ELF leaves 225 free SPIFFS
blocks. Seven exact-byte normal and ASan/UBSan replays retain metadata name reads
193, healthy-SD first-frame reads 205, timer fallback 225 and fallback 320.
Cold-SD filename reads increase by one, from 1,687 to 1,688. These host counts do
not assert a physical-device speed or hardware qualification.

## Reproduction and final gate

Run `minimal/test/mounted_files_097_final_test.py` with the exact .96 baseline,
published Files build/source, pinned assembly tools and Runtime source. It
includes the 207 source/byte preservation probes plus eight product-publication
rejection checks. Original preflight reproduction remains separate.

`compose_mounted_files_097_final.py` requires clean exact source checkouts and
produces a full image only after independent SPIFFS decode, bank-state digest
checks, preserved flash-range checks and all 46 selected SD source checks.
Final naming requires a read-back product publication receipt binding repository,
branch, exact commit and tree. Before product publication, `--preflight-only`
produces only an explicitly labelled local test image.

Use `verify_mounted_files_097_final.py` for independent final readback, then
`qualify_installed_catalog.py --provider-capacity 40 --shared-files` with the
matching native BIN/ELF, generated store/SD and composition receipt. All 42
internal and 46 selected SD ELFs require strict role/import admission; four
namespace mutations must fail. No hardware or provider execution occurs.

## Installation scope

The final raw BIN is 16,777,216 bytes, a FULL INITIAL image at offset 0x0.
It erases internal settings, saved networks and app data. It is not a preserving
update. No new SD overlay is required relative to delivered .96. The existing
.96 thirteen-manifest overlay must already be present; an older SD tree is not
the qualified baseline. Do not format the card or remove its contents.
No physical device or user computer is accessed by this build.
