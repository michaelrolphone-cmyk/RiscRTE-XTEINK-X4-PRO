# MSC 0.1.6 target checkpoint over combined .1.78

This supersedes the earlier source-only checkpoint's preparation-test blocker.
No full firmware is emitted and no hardware success is claimed.

## Source and target binding

- X4 baseline receipt: `8e9e8eb7a2b1f7f860777d0d0e8a89dd2822af87`.
- Shared MSC fix: Reader `4c2e2dbe3bf587b51873c65a1a1c3faf4035e884`.
- TinyUSB: `1eb6ce784ca9b8acbbe43dba9f1d9c26c2e80eb0`.
- GCC: esp-2021r2-patch5 8.4.0; Arduino framework
  `3.20017.241212+sha.dcc1105b`, IDF 4.4.7.
- Uncompacted ELF: 65,172 bytes, SHA-256
  `a737270169330823a4a66aa996d9f027fc1e5645f5528e4de9f7712b44bdd275`.
- Compacted/package ELF: 34,880 bytes, SHA-256
  `dd045f3a828048e82d14676757e54a6dab06d01e00b6a3711d28172b4f8ce567`.

An independent rebuild of original Reader 45cf61ac through the same SDK/compiler
and loader-metadata-v3 compactor exactly reproduces the shipped .078 MSC ELF
`f791783ac4e21d61c0da4576aef091af2d218d7cd84c4e6ac2f0f36b09a00dac`.
Thus this target is grounded in the actual selected binary, not just its version.

The ordinary package and catalog are in `evidence/msc-cleanup-078/target/`.
They preserve the canonical driver ID and provide usb.device.msc@1 with version
0.1.6, digest-bound ELF and ABI/import sidecars. They are unpublished test
packages, not an instruction to hot-replace an active/retained driver.

## Qualification and preservation

The target build passes import/export checks, Xtensa relocation validation and
PSRAM unsafe-atomic exclusion. Verified compaction preserves allocated sections,
global/weak symbols and every retained relocation. Strict loader-map audit passes.

`qualify_msc_cleanup_078.py` validates exact combined image and SD ZIP hashes,
extracts the baseline store, and changes ONLY `usb-msc/driver.elf` and its manifest.
All 16 SD apps, Reader, Daily Paper, launchers, scene, native binary and panel 0.1.12
remain byte-identical. No old Reader or Daily-only image is used as the baseline.
Normal and UBSan runs each admit all 54 modules, reject wrong roles and unsafe
operations, reject each missing MSC import, and admit both .078-to-candidate and
candidate-to-candidate cohorts with 38 internal ELFs and zero hardware/storage
calls. Cohort metadata remains .078 solely for staging qualification; a future
firmware delivery must assign its own product identity and paired-store hashes.

The preparation assertion was a fixture defect: it combined USB snapshots with
paper-clock ordered touch events. System-Apps commit `301c20e` repairs only that
fixture; all eight normal/UBSan preparation cases pass without weakening any
custody, release or Home assertion or changing production app bytes.

## Reproduce without building firmware

1. Check out Reader 4c2e2dbe and pinned TinyUSB. Run
   `scripts/build_usb_device_msc.py --tinyusb TINYUSB --framework FRAMEWORK
   --cc XTENSA_GCC --output NEW_TARGET` using Python with pyelftools.
2. Run `minimal/scripts/qualify_msc_cleanup_078.py --baseline FINAL078
   --target NEW_TARGET --reader READER --runtime RUNTIME --tools TOOLS
   --output NEW_QUALIFICATION`, with NATIVE_DRIVER_CC set to that compiler.
   FINAL078 contains the exact combined image, paired native.bin and full SD ZIP;
   Runtime is 7071f0c25e223f24670bed409a5f8b6f291c8042. TOOLS is the .078
   WatchAppTools source used by its receipt. Default sanitizer is UBSan.
3. Preserve the generated source/package/inventory qualification receipt. A later
   approved full-image assembly must use this exact compacted ELF and manifest,
   preserve all other payloads, update product/cohort identity and paired hashes,
   and independently read back the store. No full image was made in this task.
4. Still required before closing the issue: physical Windows safe removal,
   retained Stop retry, pending reads/writes, remount and CDC re-enumeration.

## Host limitations

The normal and UBSan macOS checks described in the earlier RESULTS remain valid.
ASan timed out; Linux fixed-address DWC2 and full dynamic lifecycle qualification
are not claimed. The local Docker daemon reports Linux arm64 but test containers
remain in Created with no PID; even a no-network echo cannot start. No unrelated
container or daemon state is modified. Existing runtime port/binding and pinned
HWCDC restoration tests passed separately. These limits do not justify weakening
reset, ownership, remount or Home guards.
