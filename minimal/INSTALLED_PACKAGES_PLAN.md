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


## October 11 native/provider checkpoint

Published source on the isolated feature branches:

- Runtime `09b78ca39e19152a3bd1ac3a02a390fcb3a00cbd`: owner-envelope native
  installation transactions; no app identities in that envelope; stable policy
  admission/withdrawal; active-target protection; resident-return registration
  regression; missing/empty/oversized manifest handling.
- System-Apps `eda631c7255dcc1f0802fdced68baed838a4f61c`: experimental cache-backed
  provider; zero SD calls on cache startup; complete-scan transaction; protected
  uninstall preflight; source-bound Xtensa builder and host integration tests.

`evidence/installed-packages/provider-target-link.json` records a clean-source
build of the provider (53,844-byte ELF). This is target-link qualification only,
not a runnable X4 image or hardware qualification. The generated ELF and receipt
are also in the isolated task's `build/installed-apps` directory.

Passed: normal and UBSan native removable launch suite, including existing
foreground launch/return then newly discovered package admission and two launches;
metadata scanner failure/retention suite; installed catalog codec/media/fallback
suite; cache-backed provider integration suite. ASan on this host stalls inside
its own initialization, so no ASan pass is claimed.

### Explicit nonblocking UI requirement

The panel-settled synchronous Springboard prototype was removed. There are no
changes to current Springboard/display/input code, no new application-identity
whitelist, and no firmware rebuild or flash in this checkpoint. The full acceptance
case (background refresh then visible icon then launch with unchanged firmware)
is NOT complete.

Required next sequence:

1. Add scoped asynchronous storage operations and lazy SD activation. Current
   `x4pro_sd/driver.c:start` invokes `init_card`; merely queueing enumeration does
   not remove that first synchronous stall. Respect existing owner-only native
   GPIO/SDMMC/sync contracts; no global owner relaxation. Results/cancellation
   must prove quiescence before release, launch, USB export or sleep.
2. Bind the completed async provider through the existing shared app adapter.
   Show cache immediately; copy/publish snapshots at logical lifecycle checkpoints
   independent of physical panel settling, and preserve touch identity across a
   catalog generation change. Validate unknown installed package to background
   catalog to actual launch on the target integration.
3. Add App Store installation validation/receipts and durable per-app namespace
   allocation. Current native envelope intentionally rejects namespace-owning
   storage grants until there is a durable allocation protocol.
4. Complete core app/driver SD-first provisioning with internal bootstrap closure
   and atomic graph activation. The published offline planner does not implement
   on-device driver installation.
5. Complete shared SD-first settings/AppData with migration, internal fallback,
   and retained pending writes across SD removal/USB export as a separate milestone.

Do not promote this checkpoint as a discovery-capable release. Compose against
`.1.78` delivery source `8e9e8eb7a2b1f7f860777d0d0e8a89dd2822af87` after the above
boundaries are complete; its independent immediate build workspace was untouched.
