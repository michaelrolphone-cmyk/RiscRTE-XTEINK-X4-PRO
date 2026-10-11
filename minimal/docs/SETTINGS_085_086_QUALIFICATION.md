# Preserving .85 bootstrap and .86 settings successor

Software qualification only. No device access, flash, master merge, GitHub Release or public feed publication occurred. The previously delivered .84 artifacts are unchanged. Product .85 is the preserving bridge; .86 is the feature successor.

## Exact compiled sources

- Runtime 0.2.18: `8d713b52edca004e1d53bf30a1c584859fe33d14`.
- System Apps source: `c3d3aad0768e98eed968fc3e6ec87929dd1fd621`. The catalog 0.8.0 binary was rebuilt from this tree and matched the earlier build byte-for-byte. Later System Apps checkpoint `a8bc0c3` adds a removal/reinsertion test only.
- X4 .85: `8d69787e393dd48270dd6004d882aba25e0b5cd6`.
- X4 .86: `4103d2f10489e0f3cb51ce49399d84500a7ae889`.
- Drivers: `39b9be00528c404af63c8f654d1bd2b29cf73b18`.

Later X4 commits correct a stale hosted CI Runtime checkout and add qualification tests, receipts and this document; they do not change the compiled payload. Individual unchanged Home 0.4.10, Springboard 1.8.2 and SD 0.2.21 artifacts retain the source receipts shipped with .84. Every assembled store and full image has independent digest/partition receipts.

## Settings behavior

The production backend now migrates existing eligible private namespaces, including opaque values up to the existing backend limit of 2048 bytes. Its PSRAM map and paged SD format have no 16-key namespace cap. Migration enumerates one original key per owner step. Original NVS values remain a read-only recovery backup. Successful writes commit per-key native deltas before reporting success. Verified immutable SD pages plus an atomic index form the checkpoint; the native anchor advances only after verified close, and only covered deltas retire. Concurrent newer writes remain journaled.

Cold restore of an anchored namespace needs its SD base and fails closed if it is missing or corrupt. Exported/removed/unavailable media never creates a divergent NVS value store. Resource exhaustion returns an error instead of truncating values. Private namespace ownership remains unchanged; shared system/radio/provider namespaces are outside this migration. The private ledger currently admits 128 slots; scalable settings does not imply unlimited installed-app slots or unlimited NVS journal capacity.

## Why the bootstrap is serial

Inspection of the actual delivered .81 and .83 updater application and provider proved their feed is compiled empty. They have no runtime URL setting. Publishing a catalog alone cannot enable those old UIs.

The two .85 bridge stores retain their respective actual delivered baseline and replace only the OTA app and firmware-update provider with explicitly feed-enabled versions. They preserve prior capability declarations and admission policy. The .86 successor adds scalable settings and the previously qualified dynamic catalog/app work. The .85 firmware-update UI can consume .86 after approved catalog/release publication. The shared Watch/default profile is not silently given this X4 URL.

## Existing serial/native preserving entrypoint

`minimal/scripts/prepare_preserving_serial.py` is offline only: it never opens a port. It requires a fresh 16 MiB readback, an exact whitelisted .81/.83 baseline, a confirmed OTA selection, matching bootloader/partition bytes, a valid active-bank record, and exact active firmware/store hashes. It rejects changed or unknown devices. The selected existing bootloader supports rollback and is byte-identical to both baselines.

The planner emits inactive firmware, inactive store, inactive bank record and a separate OTA-selection sector. It proves sector-rounded writes exclude bootloader, partition table, NVS, AppData, the active pair and its bank/OTA records. Existing esptool transport can stage the first three with `--after no_reset`, read back and verify every byte, then write and verify the selection sector LAST before reset. Never use `erase_flash`, never combine selection with staging, and never reuse a software-fixture plan on a device. A current device snapshot must produce a new plan. Candidate files must match the qualified package SHA256 list; the planner's bounds checks are not independent ELF admission.

No serial transport or power-cut test was performed on hardware. The offline test covers both original baselines, both active banks, 1660 staging-sector boundaries and 33 selection-byte cut points per case, protected-data canaries, source-integrity rejection, and the existing NEW/PENDING_VERIFY/ABORTED rollback-selection model.

## Verification

- Both complete target native builds passed through pinned PlatformIO preparation.
- Strict .86 admission covered 42 ELF modules and actual native imports. Actual .81/.83 -> respective .85 -> .86 transitions each admitted 42 ELFs with zero hardware/storage calls.
- The linked 64-byte V2 migration record, selected function and exact source/target snapshots passed verification.
- Actual Runtime broker dynamically launched a newly installed SD app not compiled into firmware, preserved 32 original settings and grew them to 65. Existing removable-media/launch/error cases pass.
- Core settings tests migrated 513 values and grew to 1027 keys, including old-format pending journal import, concurrent acknowledgement, uncertain persistence and CRC rejection.
- Production NVS adapter tests cover original-value enumeration, per-key delta/anchor reload, retained originals and initialization faults without erasure.
- Actual catalog/checkpoint/worker tests cover 153 migration interruption boundaries, 98 original values including a 2048-byte value, export exclusion, missing-media delta retention and reinsertion replay. Earlier catalog/provider tests retain their 65/110 interruption cases.
- `run_qualified_update_service.sh` runs the actual feed-enabled shared update service and production paired-bank transaction against each actual .85 assembled fixture, the draft .86 catalog and exact cohort payload. Both pass catalog availability, download streaming, SHA/readback, activation/restart and unchanged old pair. HTTP, flash and boot selection are boundary models; this is not hardware execution or a GUI touch test.

## Packaging and remaining release steps

The .86 full image is a fresh-install image at 0x0 and ERASES NVS/AppData; it is not a preserving update. The SD archive is an overlay: keep existing user files and old provider images for rollback. The bootstrap package has baseline-specific candidates and no ready-to-flash device selection plan. The .86 cohort and catalog fragment are review-only. Merge the fragment into the existing catalog without dropping apps or unrelated releases; do not replace the entire live feed with its empty `apps` list.

Remaining: review/approve release assets and feed, publish the exact .86 assets/catalog, obtain a real device readback for the preserving plan, and separately authorize/perform hardware transport, boot-health and UI verification. Hardware display/input performance is unmeasured; unchanged UI artifacts and cooperative storage boundaries were retained.
