# X4 native ESP-IDF 6.1 candidate

This product profile migrates native startup/build selection to the shared
Arduino-free Runtime. It is a **new candidate**, not the released 0.1.121 image,
not a byte-exact replay of its missing composition record, and not a device
qualification or permission to flash.

## Source boundary

- Product baseline: `3ac013bd21815bf18e42466b656dbc333665bf6b`, release
  `test-t064-crash-0.1.121`. Stale main `9230437f` is not this baseline.
- Actual released native Runtime: `f734d91780cdb4f1ba36fe82dcbd8fa28f25bb2b`
  (0.2.28). The T064 workflow's `a91edf3f` is a Home/tooling input.
- Released native: 1,665,248 bytes, SHA256
  `2e6116022ef7f8b35018ec42aebeefb831560d88be0c1d3b191946ab35840d6a`.
- Released composition marker:
  `3badafa462a1881d34514dd46454b0535ef48a8739310599fafb00c59b7319a1`.
  The original complete composition JSON and native ELF have not been recovered.
- Released factory SHA256:
  `48145adc023a334885207100ce29596edef3f02c07a6d830ca53e3ab1fbf5993`.
  Its embedded cohort source is `7032d7bdfc0ada3e5dec5aafa757a534ab91abe8`,
  which is distinct from the release-tag source above.
- New SDK: official ESP-IDF v6.1, source
  `fff9895c82d744c7237be8847347bdd1b07c6643`; GCC 15.2.0,
  crosstool-NG `esp-15.2.0_20251204`.

`released-profile.json` records the audited source selections and their evidence
limits. `released-byte-facts.json` records decoded native image facts.
`preserved-inputs.json` pins the unchanged released rail, board-power and selected
panel inputs. Cache selection follows explicit T054 documentation; the unavailable
original ELF is not claimed as independent cache evidence. Optional export-migration
authority is not inferred or synthesized.

Configure from clean committed product and Runtime checkouts. CMake writes a new
`x4-native-idf61/selection.txt` and `X4NativeBuildIdentity.h` to the build directory.
Their new composition digest covers exact product/Runtime commit identities,
selected definitions/link options and hashes of product-native input files.
It is a selection/provenance record, not a complete dependency inventory or proof
that an uncommitted Runtime checkout equals its HEAD. Final release evidence must
bind the clean dependency commits, SDK configuration, ELF and BIN hashes as well.
Use `RISC_X4_SOURCE_SHA` and `RISC_SOURCE_SHA` only for the exact corresponding
checkout commits when CI cannot query Git ownership safely.

## Preserved product selections

`profiles/native-idf61.cmake` uses Runtime's `idf/product-profile.cmake` contract.
It selects the released standard-store target `esp32s3-16mb-appdata-iq`, paired
ABI2, 24 policy/requirement rows, 64 apps, 40 providers, image cache, HTTP, IQ,
SDMMC, USB PHY, TCP/entropy, 512-byte retained wake, panic evidence, diagnostics,
native package volume, app-data, and the selected native settings lifecycle.
Stack-usage output and released linker roots/wrappers remain selected. SDK flags,
GNU++17, 16 KiB owner stack, QIO/80 MHz flash, octal/80 MHz PSRAM and 240 MHz CPU
are the shared native SDK contract. Native VFS wrappers additionally cover the
SDK 6 registration entry points through shared Runtime.

The exact released CSV is product-owned:

- app0: `0x10000 / 0x260000`; appdata: `0x270000 / 0x80000`
- bootfs0: `0x2f0000 / 0x510000`; app1: `0x800000 / 0x260000`
- bootfs1: `0xae0000 / 0x510000`
- `0xa60000..0xae0000` remains unassigned; trailing flash is not repurposed
- NVS, OTA selection and bank-state addresses/sizes remain unchanged

`native-idf61-settings.h` owns exactly the released 16-byte logical owner
`X4-RTE-SETTINGS` plus byte 1, volume instance 9, writers `settings`, `paper_clock`,
`battery`, `ble_scanner`, `contexts` in namespace 1 and `wifi_settings` in namespace
6. Shared Runtime keeps the exact app-data mount and private settings root, with
no automatic format, growth, or unconstrained writer fallback.

No native display backend is introduced. The unchanged admitted board-power
provider still claims/verifies/holds GPIO1, transfers permanent CPU custody and
publishes `board.power.ready` before dependent providers. The selected UC8279
`x4pro-uc8279-fast` 0.1.12 provider and its BUSY/completed-frame contract remain
product drivers. Display, touch, SD and frontlight selections are not rebuilt or
silently substituted by this native profile.

## Native startup checkpoint

The existing `--wrap=app_main` hook remains. Its eight rail operations stay in
order: stage HIGH; direct digital latch/OE/matrix/IOMUX; RTC deinit; reassert HIGH;
physical HIGH check; unhold; hold; physical HIGH check. The digital primitive is
byte-identical source and must have no nested calls in the linked image. No
failure path clears ownership or performs blind rail cleanup.

IDF initializes hardware, cores, heap and PSRAM before entering this wrapper.
After the rail attempt and bounded initial boot-log capture, the wrapper calls
`risc_x4_native_ready` explicitly, then the original native `app_main`. This
replaces the framework-complete checkpoint formerly supplied by `initVariant`.
It preserves failure latching: the ready checkpoint cannot clear a rail error,
and Runtime's existing `risc_native_startup_error` gate refuses normal bootstrap.
This is not a ROM, bootloader, or pre-IDF hook.

The RTC record remains 264 bytes, including checksum and first-display evidence.
Existing numeric phase values remain unchanged; new phase 5 says `native-ready`
so recovered phase 3 still truthfully says `arduino-variant`. The existing
`variantUs`/`variant_us` timestamp slot carries the framework-ready time without
a layout change. The offline boot-log extractor recognizes both checkpoints.
Observers remain bounded and separate from drain/file/NVS persistence. The
legacy Arduino path retains its original callback for historical qualification.
The deprecated SDK single wake-cause API is intentionally retained here to keep
the recorded enum semantics; changing it to a bitmask would alter the log ABI.

## Build and checks

Use the shared native Runtime candidate checkout and its pinned SDK/toolchain.
Do not overlay this product onto the old `migration-source.json` Runtime input.
Use a separate build directory; never reconfigure another active product build.

```sh
export RISCRTE_RUNTIME_ROOT=/absolute/path/to/native-runtime
export X4_ROOT="$PWD"
python3 minimal/test/native_idf61_profile_test.py
python3 minimal/test/run_native_idf61_boot_test.py
SANITIZE=1 python3 minimal/test/run_native_idf61_boot_test.py
bash minimal/test/run_bootlog_test.sh
idf.py -C "$RISCRTE_RUNTIME_ROOT/idf" -B "$X4_ROOT/build/native-idf61" \
  -D RISC_PRODUCT_PROFILE="$X4_ROOT/profiles/native-idf61.cmake" build
python3 minimal/test/verify_native_idf61_target.py \
  --elf build/native-idf61/riscrte_native.elf \
  --selection build/native-idf61/x4-native-idf61/selection.txt \
  --output build/native-idf61/x4-startup-proof.json
```

The final-ELF checker binds the actual IDF task/wrapper/native-ready/gate/observer
call edges, ordered rail calls, no-call digital primitive, 264-byte RTC section,
and fresh product/Runtime identities. It rejects five linked call-bypass
mutations. Its small synthetic Xtensa test can be run against a configured
selection using `native_idf61_proof_fixture_test.py --selection <selection.txt>`;
that verifies the checker, not a product image.

Initial source qualification: all 72 native hold/mux/failure combinations,
readiness ordering/idempotence, reset/corruption/first-display tests and native
checkpoint offline recovery passed normally and under ASan/UBSan. Released
Arduino startup regression and persistent boot-log recovery tests passed.
The production overlay compiled with SDK 6.1/GCC15.2; its digital staging object
contained no nested calls. The profile regression verifies exact audited
features, partitions and settings bytes plus unchanged rail/board/panel sources.
The synthetic linked-checker fixture is separate evidence. A full X4 target
build, final product-linked proof and hardware behavior remain to be qualified.

## Packaging boundary

The source-only [0.1.122 successor packaging gate](PACKAGING.md) recovers the
actual released internal and complete-SD inventories, requires new native
source/ELF/BIN/MAP closure and preserves the existing device-MSC workflow.
Its separate factory/old-bootloader qualification boundary replaces no
historical evidence and emits no preserving SDK-migration kit.


Do not run T064's unchanged-native assertions on a newly built native image.
That release recipe changes only Home/default ELF, manifest and cohort over its
exact 0.1.120 base. New native bytes require new cohort/native provenance and
separate qualification. Complete-SD packaging source
`3f9edae04fb548eb3d6acc7eb8ca1a63ef5d5c72` is also separate from the firmware source;
its byte-preservation recipe is not a native SDK build. Existing preserving-update
restrictions, protected ranges, user data and inactive-bank ordering remain
product-owned. This profile does not change release workflows or provision a device.
