# X4 OBD integration preparation

This is preparation evidence, not a release or device qualification. Product
0.1.97 is reserved for the higher-priority Files fix. Final OBD product 0.1.98
must be composed from that delivered source and receipt, preserving its native,
Home, Files, startup packing and SD lifecycle behavior.

## Component lineage

- OBD application: Utilities PR64, source 65d2ccf2c0eb5179a00d87544c519d9daa6a6b6d,
  with integration fixes published as 0.2.1 on working branch
  `feat/x4-obd-reconnect-021`, commit
  `5e37261dc400c21d302662ab72d53ccba099d946`.
- Scene telemetry: System Apps PR106, source
  3bdd59be0bfb4a6e726616e075ace667bf52cd37. The telemetry implementation is
  combined with current System Apps 7870df1ae0272cf180f454392927b997f2553846.
  Scene 0.4.1 retains the newer native exit handling and clipped/color painting.
  Replacing the current scene with the historical 0.4.0 binary would lose those
  fixes and is not the composition used here.
- BLE serial: Drivers source 8ec572af94ee6e844b1685d8d050471cd58cad87,
  provider 0.1.0, SHA256
  cc5bf2a38bf655c1cb51cbdaf3eacbffff69b852adbfb57363ee366cc453ef1f.
- Current native Runtime: 6377d498a47b59dac8ad85d930983fffc6c8baa5,
  version 0.2.24. Historical X4 .88 recipes are comparison evidence only.

## Narrow deployment changes

The app requires `ui.scene`, `bluetooth.serial`, and SD volume 9. Add one explicit
boot catalog-authority reservation for its exact SD path and manifest, an
explicit resident-foreground entry, and the BLE serial provider. Update both the
internal scene image and its selected content-addressed SD image. Retain the
old immutable SD provider files. Do not broaden the general installed-app or
installed-provider grant envelope, change the private-storage namespace range,
or enable the previously opted-out shared-settings behavior.

The SD overlay contains only four new paths: the app ELF and manifest, the new
scene ELF, and BLE serial ELF. Existing applications, manifests, books, fonts,
ROMs, saved state, and rollback provider files remain. All metadata introduced
by the .96 SD foreground-lifecycle repair must remain byte-identical.

## Evidence available before final Files baseline

On the delivered .96 baseline, a preflight composition passes native cohort
validation for 43 internal ELFs and strict role/import admission for all 48
selected SD images. Actual native catalog tests cover dry-run and committed
registration, idempotent discovery, foreground lifecycle selection, the three
specific OBD grants, and rejection of changed paths or grants. No target
instructions, Bluetooth radio, SD hardware or vehicle are operated by these
host checks.

The combined scene passes 179 presenter/profile executions, existing component,
Reader and checkpoint checks, plus normal and ASan/UBSan telemetry checks. BLE
serial passes 10 real-NimBLE protocol cases in each of normal and ASan/UBSan
modes. All 16 app scenarios pass in both modes, including four added reconnect/recovery
cases. The late-SCAN_DONE reconnect failure was reproduced before the fix.
Poisoned BLE state now stops retries and requires closing OBD and restarting the
device: demand-retained provider pins mean app reopening alone cannot promise a
fresh provider. Failed close still retains the invocation and BLE custody.
Final source/build receipts must be added before delivery.

All final checks must be rerun on the exact published component source and the
qualified .97-derived .98 composition. Preliminary evidence must not be labeled
as final-image qualification or physical adapter compatibility.

## Adapter and hardware boundary

This implementation uses BLE GATT serial. Classic Bluetooth SPP, Wi-Fi ELM
adapters, authenticated/pairing-required endpoints, or unknown vendor protocols
are not established by the existing transport fixtures. The physical adapter
must be identified and tested by the owner before claiming compatibility.

The app retains explicit confirmation and fresh stopped-vehicle/stopped-engine
checks for diagnostic-code clearing, plus positive ECU acknowledgment. No
vehicle code-clearing action has been performed during development.

A full-initial image, if delivered, is flashed at offset 0x0 and erases internal
settings, Wi-Fi and app data. It is not a preserving update. Install only the
paired qualified image and SD overlay after reviewing its final instructions.

This historical preparation record is superseded by OBD_098.md.
