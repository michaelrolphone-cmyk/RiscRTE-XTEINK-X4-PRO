# X4 .84 software test qualification

Built product source db034640e7cd9291d63e593cb59af48bb079d584 with Runtime 2bcc2094808f9770e83eb84205a75c5407aeb0cf (0.2.17), System Apps 4a24bc43afcdfa70a48b5a9ee5dfefc9a109c4a8 and Drivers 39b9be00528c404af63c8f654d1bd2b29cf73b18. CI 38143166495 passed. No hardware flash, master merge, release or public catalog publication.

Actual delivered .81 and .83 archived full images were independently unpacked, rather than using earlier staging stores. Both have installed-app discovery and namespace ownership already. Their old provider images remain in the matching SD overlay. Full image is a fresh 16 MiB offset-0 image and erases NVS/AppData; it is never a preserving payload.

The native contains the existing shared V2 export migration record generated from actual .81 and target .84 metadata. The linked 64-byte record, selected function and both authority snapshots were verified. Standard complete native metadata admission passed from both deliveries: 42 ELFs, zero hardware/storage calls.

The new 16-key limit belongs to SD snapshots, not existing NVS. Runtime now detects a populated native namespace without enumeration or rewriting and leaves it native. Real Runtime broker tests retain 32 original keys and grow to 65 across repeated launches; production NVS adapter tests round-trip 64. New namespaces use SD snapshots; existing large native namespaces are not truncated or silently migrated.

`test/deployment_payload_test.cpp` reuses the existing shared paired-bank test backend and exercises production PairedBank.cpp with actual delivery/full target payload bytes. Both native-only clone and cohort paths pass 12 selected I/O fault cuts, RAM restart/retry, and old-bank rollback checks from each delivery. Further runs start from a modeled native bridge with unchanged original store. Boot selection/flash and validation boundaries are model doubles; separate strict admission and native proof check real images. These are not actual bootloader or hardware execution tests.

Compile with RISC_PAIRED_APP_DATA=1, runtime/test, runtime/src and runtime/sdk/driver include paths, OpenSSL, and UBSan. Link runtime/src/runtime/update/PairedBank.cpp. Invoke with BASELINE_FULL.bin TARGET_FIRMWARE.bin TARGET_BOOTFS.bin. Each run checks native clone (6631 I/O) and cohort (7928 I/O). The model cannot write NVS/AppData; distinct canaries verify unchanged memory, not a hardware preservation claim.

## Deployment blocker

Delivered X4 UI rejects runtime-only catalog entries. Native bank API accepts a higher runtime with unchanged cloned store, but this is only an API-qualified bridge. Product cohort versions strictly increase. A usable catalog route therefore needs an approved version allocation (for example .84 bridge then .85 feature image), new builds and hashes, or separately authorized updater work. Do not advertise the included .84 API test as an end-user OTA bridge.

The Library packages include exact unpublished firmware catalog fragment and release asset hashes/destinations. Merge the fragment into the existing release-index preserving app rows only after approval and resolved routing. SD provider install descriptors remain a separate source, not a public catalog published by this work.

## Delivered updater entry point correction

Inspection of BOTH actual archived .81/.83 updater/controller and provider ELFs shows the disabled-feed controller message and no catalog URL. The shared X4 disabled-feed test passes under UBSan: refresh creates an empty list with no HTTP request; begin cannot start a row. This is more restrictive than the runtime-only parser issue above. Merely allocating increasing product versions or publishing a cohort catalog cannot update these delivered binaries. There is no qualified end-user UI sequence in this task.

Reserved product .85 for a future compatible bridge, .86 for its successor, preserving the existing .84 artifact. Existing project bridge .82 retains its old meaning. No new bridge firmware or public catalog has been published. The entry point requires separate preserving bootstrap qualification or installation of feed-enabled updater code; no device action was performed.

### Exact SD settings semantics

Existing native namespaces: reads AND subsequent writes go directly to original NVS. No SD migration, mirror or checkpoint occurs for LegacyNative. This is preservation fallback, not completed SD-first migration.

New installed private namespaces: a successful write first commits a native recovery journal and updates RAM. A later asynchronous owner pass writes `/AppData/<app-id>/settings.kv` on SD, verifies bytes and closes the worker, then replaces native value payload with a small generation anchor. Thus SD is the eventual complete checkpoint, but writes are journal-first, not direct-to-SD. An initialized dirty journal survives unavailable SD; a cold namespace requiring an absent checkpoint does not silently recreate defaults. The new snapshot supports only 16 keys with 64-byte values. Existing native data is not squeezed into that format.

Remaining SD-first gap: unbounded/capacity-compatible migration of all existing keys and values with crash-safe handover and rollback. The .84 preservation fix deliberately does not implement that migration.
