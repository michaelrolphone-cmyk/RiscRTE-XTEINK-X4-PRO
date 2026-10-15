# X4 0.1.122 native SDK 6.1 packaging gate

This is a source-only successor recipe. No new firmware image, release, catalog
entry, preserving update, or hardware qualification is produced by this source
checkpoint. Runtime 0.4.0 and a clean committed X4 0.1.122 profile must first be
built and pass every gate below. No full firmware build was run for this recipe.
The active SDK migration build directories are not modified.

## Recovered released composition

The immutable baseline is release `test-t064-crash-0.1.121`, product source
`3ac013bd21815bf18e42466b656dbc333665bf6b`. Its actual full 16 MiB factory is
SHA-256 `48145adc023a334885207100ce29596edef3f02c07a6d830ca53e3ab1fbf5993`.
The [published factory](https://github.com/michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO/releases/download/test-t064-crash-0.1.121/X4-0.1.121-T064-Crash-Reports-factory-erases-data-0x0.bin) must match that full-image digest.
Its embedded cohort source is separately
`7032d7bdfc0ada3e5dec5aafa757a534ab91abe8`. The native bytes are 1,665,248 bytes,
SHA-256 `2e6116022ef7f8b35018ec42aebeefb831560d88be0c1d3b191946ab35840d6a`,
from Runtime `f734d91780cdb4f1ba36fe82dcbd8fa28f25bb2b` / 0.2.28.
The released native ELF and complete historical composition JSON remain missing.
This recipe does not reconstruct or claim either historical artifact.

`released-baseline.json` is recovered from the actual released bytes and records
all 107 internal files, the 43 ELF import sets, partition/bootloader region hashes,
app descriptor, and bank layout. The T064 assembly recipe only replaced Home,
its manifest, and cohort over 0.1.120. Its unchanged-native assertions must not be
used for this SDK transition.

The full matching card package is the separately published
`X4-0.1.121-Complete-SD-Keep-Existing.zip`, 10,844,318 bytes,
SHA-256 `2b6dce3efb468f3cd728b50707e0c9552d84e225b65e2b27e683d3d726bc6cef`.
The [published complete SD archive](https://github.com/michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO/releases/download/test-t064-crash-0.1.121/X4-0.1.121-Complete-SD-Keep-Existing.zip) must match that digest.
Its 77 paths and 49 ELF import sets/roles are pinned in the same contract.
The complete-SD source recipe is
`3f9edae04fb548eb3d6acc7eb8ca1a63ef5d5c72`. An unchanged package is delivered
under its original name and digest, not relabeled as rebuilt apps or drivers.

## Retained behavior and data boundary

Only the resident native image, bootloader in the factory path, paired bank
record, and internal `cohort.json` change. Every other internal payload and every
SD byte must be identical to the released baseline. This preserves the admitted
board-power provider, GPIO1 ownership/ready dependency, UC8279 panel, touch,
frontlight, SD instance 9, application grants, crash namespace 62, and existing
`usb-device-msc-esp32s3` external provider. Device-MSC SD access remains the
existing user-selected USB SD transfer workflow. No private USB host-controller
policy is enabled and no standalone legacy T5 port is included.

The exact settings owner bytes, namespace 1/6 writers, 24 policy/requirement rows,
40 providers, 64 applications and ABI2 partition geometry remain selected.
NVS, app-data, the inactive/active bank ordering, unassigned 0xa60000–0xae0000 gap
and trailing flash are not repurposed. SD installation remains merge/replace
of the matching package paths without formatting or deleting unrelated settings,
books, ROMs, saves, or extra applications. A factory image is always explicitly
labeled as erasing internal saved data.

## Fail-closed qualification

The gate is adapted from the Watch/Wave SDK6 packaging checks, with separate X4
ABI2 geometry, 24-row admission, settings/SD backends, startup proof and full SD
coverage. Generic image/admission helper source is a separate immutable source
role; no generated firmware artifacts are vendored here.

1. Freeze clean committed product, Runtime, System Apps, Drivers, ESP-IDF and
   image-helper sources by full commit, tree and recursive submodule identities.
   ESP-IDF must be `fff9895c82d744c7237be8847347bdd1b07c6643`; compiler must be
   GCC 15.2.0 / `esp-15.2.0_20251204`, with its executable hash recorded.
2. Bind native ELF/BIN/MAP, bootloader ELF/BIN, partition table, sdkconfig,
   generated config JSON/headers, app and bootloader compile databases, project
   description, flash arguments and X4 selection to exact sizes and SHA-256s.
   The selected sdkconfig must be build-owned. Verify actual compiled source
   files against their immutable source roots and reject extra roots, dirty
   inputs, Arduino components/core sources/linked symbols/maps, or private
   controller policy. Runtime-owned `setup()`/`loop()` are allowed.
3. Regenerate both BINs from their exact ELFs using the SDK6 image conversion
   flags and require byte equality. Keep the installed app-descriptor project
   identity. Require QIO/80 MHz, 16 MiB flash, octal/80 MHz PSRAM, native newlib,
   SPIRAM atomics workaround, generated rollback config in app and bootloader,
   and both health-confirmation/rollback functions. Reject new security/anti-
   rollback settings and any partition-byte change.
4. Require Runtime 0.4.0, product 0.1.122 native markers, exact source identities,
   ABI2, 24 rows, native API/SDMMC boundaries and public export tables. Require
   the final native IQ proof, DRAM registry, IRAM ISR-yield and time32 boundary.
5. Require the four zero-only bootlog copies (4,528 bytes) in native external
   BSS, with the 12 boot/persistence controls and RTC record still internal/RTC.
   Require native PSRAM boot initialization. See [BOOTLOG-MEMORY.md](BOOTLOG-MEMORY.md).
   Run the existing final-linked X4 GPIO1/startup/ready/observer/gate/RTC proof
   and reject all five linked bypass mutations. The wrapper must be compiled
   from this exact product checkout. Settings/rail/panel regression remains a
   separate source and host check; none of these checks establishes hardware.
6. Admit all 43 retained internal ELFs through production Runtime cohort logic,
   using native settings/read-through/SD capability fixtures that forbid I/O.
   Independently admit all 49 SD ELFs against the new native public resolver
   tables and exact production ELF policy. For each SD ELF, require the correct
   app/driver role and reject the wrong role, unsafe operation and every missing
   import. Both paths run normally and with ASan/UBSan. Private imports cannot
   be authorized by a sidecar or copied legacy certificate.
7. Build from fresh directories through `native_idf61_build.py`, with fixed
   sanitized commands, ccache disabled and one compiler job including bootloader.
   Require compiler-produced Ninja dependency records, all compiled objects,
   pinned Git source/header bytes, generated configuration/linker scripts,
   toolchain/ROM hashes, and exact MAP-to-ELF symbol addresses in the linked map
   region. Missing build-local Ninja inputs must be proven phony aliases by the
   exact current graph; every real child remains required and alias queries are
   retained. Missing real files, external inputs, cycles and malformed graphs
   still reject. A JSON receipt or standalone `qualify` call cannot authorize output.
8. Repack twice deterministically; require independent SPIFFS readback equality.
   Run 496 inactive-bank/torn-write/selector/corruption fault cases across both
   banks and selector sectors, including NVS/app-data/gap/trailing preservation.
   Recheck sources and native artifact hashes after qualification, before output.

Every retained ELF must pass against the final candidate. A missing export or
capability is a blocker, not permission to silently replace a retained payload.
New/rebuilt application or driver packages need their own reviewed composition.

## Factory versus existing-bootloader transition

A qualified factory candidate includes the new SDK6 rollback-enabled bootloader
and is labeled `factory-candidate-erases-data-0x0.bin`. The software model uses
a separate in-memory transition fixture containing the exact old bootloader.
That fixture is never emitted as a flash kit. The generic preserving planner
must reject the new-bootloader factory as an existing-bootloader update.

No preserving SDK-migration kit is emitted by this recipe, even when every
software check passes. The exact deployed bootloader still needs candidate boot,
health confirmation and rollback qualification on hardware. A new factory build
or software fault model cannot establish that compatibility. No device is
accessed by these tools and no hardware result is inferred.

## Reproduce source-only tests

Set paths to clean checkouts and the exact released factory and SD package.
`HELPER` can be the checked-in Watch image/admission tool repository at
`fcdb3077444f164cebea3e206fa5ae77264ecacd`; it is hash-locked again at freeze.
Python requires pyelftools and the pinned environment's CMake/compiler tools.

```sh
export RISCRTE_RUNTIME_ROOT="$RUNTIME"
python3 tests/test_native_idf61_candidate.py \
  --runtime "$RUNTIME" --image-helper "$HELPER" --sdk "$IDF_PATH" \
  --baseline "$RELEASED_FACTORY" --sd-archive "$RELEASED_SD"
python3 tests/test_native_idf61_provenance.py
python3 minimal/test/native_idf61_profile_test.py
python3 minimal/test/run_native_idf61_boot_test.py
SANITIZE=1 python3 minimal/test/run_native_idf61_boot_test.py
```

The source checkpoint passed 27 packaging tests and 14 shared provenance tests,
including the 496-case model,
the exact profile/settings/partition checks, and all 72 GPIO1/readiness cases
normally and under ASan/UBSan. Final native linked proof and new-native-bound
43+49 ELF admission have not run at this source-only checkpoint.

## Controlled native build and qualification

The sole qualification entrypoint performs a fresh build, freezes its artifacts,
and qualifies them in the same process. Both output directories must not exist.
Use the exact clean Runtime 0.4.0 successor and this committed product profile.
Do not use historical `migration-source.json`, an existing build/cache, or a
standalone frozen receipt as build provenance. The JSON receipt is evidence,
not an attestation that another process can reuse.

```sh
SOURCES=(--source "product=$PWD" --source "runtime=$RUNTIME"
         --source "system=$SYSTEM" --source "drivers=$DRIVERS"
         --source "sdk=$IDF_PATH" --source "image_helper=$HELPER")
python3 scripts/native_idf61_candidate.py audit-baseline "${SOURCES[@]}" \
  --baseline "$RELEASED_FACTORY" --sd-archive "$RELEASED_SD" \
  --output "$EVIDENCE/baseline-audit.json"
python3 scripts/native_idf61_build.py "${SOURCES[@]}" \
  --native-build "$NEW_BUILD" --compiler "$NATIVE_CC" \
  --baseline "$RELEASED_FACTORY" --sd-archive "$RELEASED_SD" \
  --candidate-version 0.1.122 --output "$NEW_QUALIFIED"
```

The build uses IDF reconfigure followed by `cmake --build BUILD -- -j1`.
`CMAKE_BUILD_PARALLEL_LEVEL=1` also constrains the nested bootloader build.
Build evidence is under `NEW_BUILD/native-build-evidence/`: source lock,
`build-closure.json` and app/bootloader Ninja dependency/input/command traces.
Qualification output includes `qualification.json` (with the build closure),
`source-lock.json`, `SHA256SUMS`, factory/native/store/partition/bootloader assets,
and the unchanged complete SD archive. It never contains a preserving update kit.
Archive the complete build directory or its dependency/input closure alongside
these artifacts; qualification JSON alone does not replace the input evidence.

Output locations must be outside source checkouts. Publication remains disabled;
version reservation, release/catalog publication and hardware operations are
separate actions. Source-only test success is not final artifact qualification.

The first official X4 clean link passed final startup, bootlog-memory and IQ
proofs with 96 bytes of DRAM margin, then correctly stopped before qualification
on an SDK-generated Ninja phony alias. The producer now records and expands
proven aliases without exempting real linker inputs. This diagnostic link is
not a fully qualified candidate; controlled CI must be rerun on the new sources.

The selected-backend correction is documented in [BACKEND-SELECTION.md](BACKEND-SELECTION.md).
The controlled producer also pins the official GCC15 generic and ESP32-S3 GCC/C++
wrappers plus the S3 dynamic configuration library. It checks their exact version,
target and multilib identity before building; qualification checks every expanded
compile command against those pinned paths. Generic drivers require an explicit
S3 configuration; the official S3 wrappers may not override theirs. Compiler
cache, child-tool, configuration and ambient Xtensa overrides are rejected.
