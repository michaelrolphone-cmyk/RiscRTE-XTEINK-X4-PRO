# X4 OBD test-readiness overlay

This recipe overlays OBD Dashboard 0.2.2 and BLE serial 0.1.1 onto the frozen
Contexts/Lists 0.1.102 union. It changes no native firmware, permissions, fonts,
other application, boot ordering or storage namespace. Resumed SD-settings work
is not part of this isolated candidate.

Exact source and predecessor hashes are in `minimal/obd-readiness-inputs.json`.
The parser/backpressure/channel fixes and hardware checklist are documented in
[Utilities](https://github.com/michaelrolphone-cmyk/RiscRTE-Utilities/blob/a9c6dfea6800676bc272c118cab80c6c41e45c9a/docs/obd-readiness/AUDIT.md).
The indication-mode correction is documented in
[Drivers](https://github.com/michaelrolphone-cmyk/RiscRTE-Drivers/blob/3a1b31c6d2cc90d7f082dd13d20ff7df77bd127c/Drivers/ble_serial/AUDIT-20261012.md).

## Reproduce

1. Build Utilities `scripts/build_obd_dashboard.py` from the pinned app source,
   with the pinned Runtime/System/Drivers sources and Xtensa ESP32-S3 GCC 8.4.0.
2. Build Drivers `scripts/build_ble_serial.py` from the pinned provider source.
3. Run `minimal/scripts/compose_obd_readiness.py` with `--baseline` set to the
   complete frozen Contexts union, `--obd-build` to the app output,
   `--serial-build` to Drivers `dist/ble-serial`, the exact `--runtime`, matching
   published Watch assembly `--tools`, and a fresh `--output` directory.
4. Run `minimal/scripts/qualify_evening_102.py` against that output, supplying the
   same Runtime and tools. It admits all 43 internal and 48 selected SD ELFs,
   runs complete normal/ASan-UBSan cohorts, and checks exact OBD/Hollow catalogs.

Composition verifies the baseline inventory and sparse-image digest, exact
public source pins and ELF hashes, manifest/authority preservation, expected
store/SD deltas, deterministic startup packing, independent SPIFFS readback,
and the cumulative SD ZIP. It streams the full 16 MiB hash without creating or
flashing a full image. Byte-identical candidate files may be hard-linked to the
immutable baseline to reduce workspace use; consumers must treat both trees as
read-only and make fresh outputs for later composition.

The app's canonical SD ELF/manifest are replaced. BLE serial selects a new
immutable SD image matching its internal fallback; the older provider image and
all unrelated SD files remain intact. Use the firmware components and cumulative
SD overlay together. A full-initial flash erases internal saved data.

These are software checks, not hardware verification. No vehicle, physical BLE
adapter or target instructions were exercised. Binary delivery remains held
until 2026-10-12 23:30 UTC. Final receipts are published separately after the
complete cohort and hosted checks finish.
