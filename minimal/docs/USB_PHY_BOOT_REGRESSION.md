# .84/.86 native/store USB PHY admission regression

The user's .84 boot failure is reproduced with the delivered .84 composed Runtime source and unchanged complete store: `missing scoped trusted platform provider`. The delivered .86 has the same fault and also reproduces. Do not publish the previously supplied .86 binaries/catalog hashes. Existing Library packages are historical artifacts, not corrected releases.

Both stores select `usb-device-msc-esp32s3` 0.1.7, requiring `platform.usb.phy.resource@1`. Both native composition receipts omit `usb_phy`; their linked ELF lacks `risc_usb_phy_resource_enabled`. Production `NativeHardware.cpp` sets the three USB PHY callbacks only under `RISC_ENABLE_USB_PHY`; `CpuPort::bind` registers the trusted capability only when those callbacks exist. The live Runtime therefore correctly rejects this store. SD's diagnostic-source and storage-worker declarations must not be removed.

The earlier host metadata harness unconditionally injected USB PHY callbacks, masking the native/store mismatch. `qualify_installed_catalog.py` now requires the exact native ELF, checks its sibling firmware.bin against the supplied native binary, reads the linked USB selector, and passes that selection to the real Runtime/CpuPort admission fixture. The fixture removes inherited USB callbacks before applying the observed selection. This correction preserves the admission rule; it does not allow missing dependencies.

Reproduction: the actual .84/.86 source/store plus disabled linked selection both fail before any hardware/storage call. The corrected .86 native build explicitly selects `--usb-phy`, retains the complete store, and passes preparation plus 42-module cohort admission. The same corrected admission configuration also prepares the unchanged .84 store. These are real Runtime/CpuPort prepare executions with inert hardware boundaries, not device boot or provider-startup tests.

Corrected native build source is X4 `6c0840f149efcc33c966da91b90e78990ce22bb4`, Runtime `8d713b52edca004e1d53bf30a1c584859fe33d14`. Build command:

```sh
python3 minimal/scripts/prepare_native_runtime.py prepare --runtime ../runtime --runtime-commit 8d713b52edca004e1d53bf30a1c584859fe33d14 --output ../build/bootfix-086-native --environment esp32s3-16mb-appdata-iq-stage --provider-capacity 40 --shared-files-transport --installed-app-capacity 64 --app-policy-rows 24 --app-requirement-rows 24 --export-migration-header ../build/increment-policy/export-migration.h --usb-phy
```

Single-job PlatformIO target build and independent full-image assembly pass. Assembly proves the linked USB selector, startup closure, partition layout, store round trip and paired record hashes. The focused test image is a fresh-install full image and erases NVS/AppData. It retains the old .86 label only as an unpublished test candidate; it is not a replacement release identity. The SD overlay is unchanged.

The separate Contexts native retention-barrier correction is NOT in this candidate. The release integrator must combine that source correction, regenerate the exact migration/source receipts and catalog hashes, run this ELF-matched prepare/admission gate, and qualify provider startup before presenting a combined working-boot candidate. No claim is made that the full startup path is fixed solely by enabling USB PHY. No device access, flash, shared merge/tag/release/catalog write occurred.
