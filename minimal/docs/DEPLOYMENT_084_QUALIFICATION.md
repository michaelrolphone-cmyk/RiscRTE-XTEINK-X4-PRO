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
