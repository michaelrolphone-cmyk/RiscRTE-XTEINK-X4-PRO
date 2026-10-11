# Dynamic installed packages: integration checkpoint

This branch is based on delivered X4 0.1.78 receipt
`8e9e8eb7a2b1f7f860777d0d0e8a89dd2822af87` on
`integrate/x4-reader-daily-078`. The receipt records assembly source
`9c074784f0eea15c92e4f791e926bdfefc55efa1`; these identifiers have different roles.
The baseline already combines Reader 0.1.8, Daily Paper 0.1.0, Scene 0.3.6,
Runtime 0.2.5 and panel 0.1.12. No firmware, SD artifact, component pin or UI
behavior is changed by this checkpoint.

## Published foundations

* RiscRTE `3c717f0`: stable-capacity native admission of previously unknown
  removable applications through existing manifest/grant validation.
* RiscRTE `d3f5087eeb38e0655bc5685214bf8c5c0b55de74`: cooperative checked-volume
  metadata discovery and offline app/driver dependency/placement planning.
  Based on the product-selected Runtime `7071f0c`, not old main.
* System Apps `bc4dbcf`: transactional app/driver metadata snapshots, medium
  availability, generation-safe selection and a policy-bound cache codec.
* System Apps `4608444c81de5020d9db49f99f615c33345aa72e`: persistence through
  existing atomic app-data replacement, with fault propagation.
  Based on Scene 0.3.6 source `dea97a7`, preserving current components.

All source branches are `feat/dynamic-installed-packages`. These are foundation
checkpoints, not a completed discovery-capable X4 image.

## Integration sequence

1. Add an explicitly authorized installation coordinator/catalog capability.
   Keep owner-granted policy separate from package declarations. Rehydrate cached
   admission under the current cohort; cache bytes alone never grant authority.
2. Bind Home/Springboard to immutable snapshots, render cached metadata first,
   and reconcile `/Apps` after first frame. Resolve selections by package identity
   and generation; preserve scrolling/display/input and existing failure UI.
3. Provide owner-safe asynchronous storage work. The bounded metadata reader is
   cooperative, not a promise that an SD operation cannot block. No scanning,
   hashing or synchronous storage service may enter the touch/display yield path.
4. Finish resident-default admission for new foreground/legacy packages,
   transactional replacement/removal, namespace allocation and cache migration.
   Native admission currently proves legacy/default handoffs; unknown packages
   must not be silently marked resident-safe.
5. Connect App Store catalog/download/install to the installed generation.
   Reuse existing provisioning Coordinator/Installer, verified HTTPS, receipts,
   inactive-bank selection and full-cohort validation. Do not create a second
   downloader or weaken existing update admission to admit arbitrary new apps.
6. Keep the SD provider, board configuration and complete transport/power
   dependency closure internally reachable. Prefer SD for remaining core apps
   and drivers; use internal placement when SD is absent, with capacity checks.
   Admit a complete driver graph before settled activation. Retained teardown
   blocks switching. Existing native primitives can support different ordinary
   drivers without rebuilding firmware; new native primitives still need a
   native increment. SD-resident driver image loading remains to be implemented.
7. Qualify the complete target composition and artifact pair, then choose a new
   firmware increment. Keep the delivered 0.1.78 baseline intact. No hardware
   operation, master merge or release is authorized by this plan.

## Evidence and limits

The production Runtime host harness prepares an empty app list, creates a new
SD manifest afterward, incrementally discovers/admit it, and executes its module
twice with fresh globals and balanced provider cleanup. Existing absent, busy,
removed, malformed and retained-close cases pass. Scanner tests cover 11 modes;
planner tests cover 12 dependency/placement cases. Catalog tests cover update,
removal, media absence, stale selection, full capacity/overflow, every byte
corruption/truncation, persisted reload and storage fault propagation.

Normal and UBSan runs pass. Scanner and catalog sources compile with the installed
Xtensa ESP32-S3 compiler with warnings as errors. Host executable mapping uses a
Mach-O shim on this Mac; this is not linked target ELF or hardware qualification.
ASan stalls before main in recursive sanitizer initialization under this macOS
malloc/dyld combination and is not counted as passed. Product-level provider,
worker, UI binding, driver activation and installation transactions remain open.
