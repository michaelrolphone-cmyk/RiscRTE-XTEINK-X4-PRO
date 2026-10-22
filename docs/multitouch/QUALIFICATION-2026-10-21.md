# X4 multitouch source qualification, 2026-10-21

## Result

The selected ordinary `x4pro-gt911` 0.1.10 provider already exposes up to five
actual contacts through `input.touch.raw@1`. Its current production source and
manifest are byte-identical to the published source at
`6590cbdcd7203ac1c2e58c84225e34d8df8602a3`. No production defect was reproduced,
so this checkpoint changes tests only. No provider, app, ABI, package version,
release input, accepted Game Boy artifact or bond behavior is changed.

- 85 provider scenarios pass normally and with ASan/UBSan (170 runs), including
  the 20,000-report independent single-touch oracle in each mode.
- 40 default HID app/scene runs pass across normal and ASan/UBSan builds.
- 14 additional runs cover two-finger right-click, pairing multitouch rejection,
  pairing GAP rejection and raw GAP recovery for the applicable two HID apps.
- Four new exact shared `PortableTouch` consumer scenarios pass in both modes:
  second-contact-before-motion after a newer unchanged snapshot, preservation
  of an independent earlier queued tap, same-timestamp UP/DOWN edges, and
  overflow/ambiguous-ACK cancellation followed by neutral recovery.
- A deliberate test-only mutation swapping the provider's new-DOWN and retained-
  MOVE phases is rejected by the shared-consumer cancellation assertion.

All 232 positive process/scenario runs and the negative mutation control are
host simulation, not device, radio, pairing-host or target instruction tests.

## Distinct source identities

| Role | Exact revision |
| --- | --- |
| X4 inspected main baseline | `6b7d1abe9b2dcc236f6086d07c0f619244c907cb` |
| Drivers inspected main baseline | `a7ae39994603c4545a3c014f09051ecfc12084d2` |
| Published selected touch source | `6590cbdcd7203ac1c2e58c84225e34d8df8602a3` |
| Ordinary-provider host SDK Runtime | `8d713b52edca004e1d53bf30a1c584859fe33d14` |
| Ordinary-provider host SDK Reader | `29276b4e1cff7819af065a77cf64805f6d5a12ce` |
| Shared consumer System Apps | `0651a55513b0aa0dff1b6a9072303def08a97378` |
| Shared HID apps/fixtures Utilities | `e80172353fcb9e6519ca9d9b2a4d43c69c1bc91d` |

The ordinary-provider SDK is the explicit `minimal/test/ordinary-driver-sources.lock.json`
compatibility input, not a resident firmware composition. The System and Utilities
sources are the current .123 contract's pins; the HID test compiles these sources,
not the retained SD app ELF bytes. Driver and consumer translation units use their
own SDKs, with exact byte equality required for the crossing `RiscTouchV1.h` ABI.

The .123 compiled producer is `93ee386b7e23628f3776edc6cfd2805cf675d649`;
its later archive qualifier is `6ff97dac5f119307a0ae63db5d2e11d09ea49516`.
The locked Runtime is `6a3b3d46f5b2857eacc6e9863799dec1f466b036`, Reader
`c98e4222048244b1e729869ed47aa99130025fd3`, Drivers
`5890721073ebabd781d5d278e447c761947a5c58`, image helper
`74f7491dc470b92dfa41fce41bf0c500f3714a94`, and ESP-IDF
`fff9895c82d744c7237be8847347bdd1b07c6643`. System and Utilities are as above.
The full source trees/submodules and artifact contracts are retained in the
qualification JSON and existing release contract, without relabeling the later
qualification as a fresh native build.

Do not overlay the native .123 sources with the historical SDK preparer: it
correctly rejects divergent `RiscProviderV2.h` copies. This is not a reproduced
native firmware failure. The historical migration pin
`34d8e694d89a1e72d8854403d8592c289fae3ddc`, `Drivers/x4pro_gt911` single-contact
migration source and the older Drivers-repository board mirror are not the
selected native product's multicontact provider.

## Existing delivered identity, not a new build

The .121 and .122 baseline inventories and .123 retention contract preserve:

- `touch/driver.elf`: 14,068 bytes, SHA-256
  `0060c1b0d3bf47d362307faf2c7b677a59a5e0ccc9dc3b0a84eada41e1e250e4`.
- `touch/manifest.json`: 704 bytes, SHA-256
  `6bfa5e918ab18d9b7c4b5d5eef4e6756b65d3f69f44bcdb7d1460f2f0f95ef1e`.
  Current source manifest bytes match this exact digest.
- Current and published provider `driver.c`: SHA-256
  `ddb898395bcfb4ca126b284f01b288274da97f34efd2e2e63c9347dff8ed4cb5`.

The .123 contract retains the complete .121 SD package, SHA-256
`2b6dce3efb468f3cd728b50707e0c9552d84e225b65e2b27e683d3d726bc6cef`.
Its BLE Touchpad ELF is `4138f2364aca210d02a81dc7427c1665fa1ba89af1c76650b39e851b704550ec`;
BLE Buttons is `2f0e6e69182b9a71a35471a35093ff69b2b26955c87032132650ed7d4895d1fd`.
These are inventory/retention observations from exact repository records. This
qualification did not redownload release bytes, reproduce their target build
closure or execute those ELFs, and does not substitute source tests for those
missing proofs.

## Test-only compatibility correction

The pinned old Utilities renderer fixture initializes only the Runtime table's
original positional prefix. With the selected newer System header, `-Werror`
rejects missing optional suffix initializers before the test can run. The X4
integration wrapper now changes that exact known fixture initializer to named
prefix fields, retaining every callback and zero-valued suffix. This is only a
copied host fixture adjustment. Production sources and warning enforcement are
unchanged; fixtures already using named fields remain unchanged.

The new shared-consumer runner records compiler commands and compiler-reported
source/header dependencies with hashes. It links the real provider and real
System reducer across separately compiled SDK boundaries. Its mutation option
writes a disposable source copy and never edits the provider under test.

## Reproduce

From the product checkout, with the exact checkouts listed above:

```sh
export RISCRTE_RUNTIME_ROOT=/absolute/Runtime-ordinary
export RISCRTE_READER_ROOT=/absolute/Reader-ordinary
python3 minimal/scripts/prepare_sdk.py --runtime "$RISCRTE_RUNTIME_ROOT" \
  --reader "$RISCRTE_READER_ROOT" --output /new/sdk
bash minimal/test/run_gt911_test.sh
ASAN_OPTIONS=detect_leaks=0 SANITIZE=1 bash minimal/test/run_gt911_test.sh
python3 minimal/test/run_hid_gt911_test.py --utilities /absolute/Utilities \
  --system /absolute/System --sdk /new/sdk --output-dir /new/hid-default
python3 minimal/test/run_hid_gt911_test.py --utilities /absolute/Utilities \
  --system /absolute/System --sdk /new/sdk --output-dir /new/hid-safety \
  --scene pair-multitouch --scene pair-gap --scene raw-gap --scene right-tap
python3 minimal/test/run_gt911_shared_consumer_test.py --sdk /new/sdk \
  --system /absolute/System --output /new/consumer --check-ordering-mutation
python3 minimal/test/run_gt911_shared_consumer_test.py --sdk /new/sdk \
  --system /absolute/System --output /new/consumer-sanitized --sanitize
```

## Remaining acceptance

A physical fitted X4 panel/configuration must actually report at least two distinct
hardware IDs simultaneously. The provider does not change controller configuration
or synthesize contacts. Physical individual lift/reorder, neutral recovery and the
intended two-finger shared app behavior remain unverified for the exact installed
candidate. No new hardware request is issued here, and Game Boy acceptance is
neither reopened nor blocked. Target build, remote CI, publication, product pins
and firmware bytes are untouched.
