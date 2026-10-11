# X4 OBD Dashboard 0.1.87

Adds OBD Dashboard 0.1.1 and reusable BLE serial 0.1.0 to the exact completed 0.1.86 image. Native Runtime 0.2.18, panel 0.1.12, Reader 0.1.8, scene 0.3.6, Daily Paper, installed catalog, private settings and all unrelated modules remain unchanged.

## Components

Utilities PR60: 1320eb2b017182d263c717f1e6b80a0fa08cf0ff; successful CI run38149396806, artifact obd-dashboard-011. App ELF SHA256 cd6049f094f9e668f2010e16794469f6544e3a2be955d8cc25b815aba0516043.

Drivers PR25: 8ec572af94ee6e844b1685d8d050471cd58cad87; successful CI run38122782755, artifact ble-serial-010. Provider ELF SHA256 cc5bf2a38bf655c1cb51cbdaf3eacbffff69b852adbfb57363ee366cc453ef1f.

The first component-only app JSON used the wrong catalog schema. 0.1.1 corrects native architecture/entry, removes unsupported fields and explicitly declares foreground lifecycle. Protocol behavior is unchanged.

## Assembly

Run minimal/scripts/package_obd_087.py with --baseline (exact .86 full BIN), --runtime (8d713b52edca004e1d53bf30a1c584859fe33d14), --tools (T-Watch-S3 db5f6c5ba1a71ed3fcc22ff29847397a050b7ee4), --app (CI target directory), --driver (CI ble-serial directory), --sd (matching .86 SD overlay), --mkspiffs, --output and --source-revision. Optional --phase is prepare/plain/sanitized/finish. No device access occurs.

Adds ble-serial/driver.elf, its manifest and obd_dashboard.json. Only boot.json and cohort.json change among the prior 103 files; 101 remain byte-identical. 33 providers fit the native capacity40. The OBD managed-directory reservation grants only ui.scene@1 and bluetooth.serial@1; the general installation envelope and private namespace range are unchanged. Existing Home/Springboard discover the SD manifest without recompilation.

Overlay the packaged Apps/ and Drivers/ onto SD, keeping existing user files and old provider images. New app: Apps/obd-dashboard/obd_dashboard.elf with manifest.json. New BLE provider has a content-addressed SD image and internal fallback. The overlay includes matching .86 apps/providers but no fonts or user state.

The full 16MiB BIN flashes at0x0 and OVERWRITES internal NVS/settings/Bluetooth bonds/AppData. Back up first. It is a fresh-install image, not a preserving OTA. Both firmware/provider registration and SD app are required. The BIN does not write SD contents. No live flash, release or public feed modification is performed by the recipe.

## Dashboard

With the vehicle parked and ignition on, close competing OBD/radio apps, open OBD Dashboard, scan and select the adapter. Discovered standard BLE UART channels are selected automatically when unique; otherwise choose the discovered vendor channel. LIVE requires ELM setup and positive ECU support/protocol replies, not merely a BLE connection.

Drive: RPM, speed, coolant, ECU voltage, throttle and load. Engine: MAP, MAF, bank1 short/long fuel trims, oil and intake temperatures. More: fuel level/rate, runtime, check-engine lamp and reported code count. Link: adapter/ELM/ECU identity, protocol and transport diagnostics. Units select mph/F or km/h/C. Unsupported/stale/waiting/paused readings show --. Pause stops new queries, Disconnect releases radio, and Quick Controls disconnect before radio handoff. Adapter/unit choices are session-only.

Only ELM setup and standard Mode01 reads are sent: no code clearing, programming or actuator tests. Requires open/unpaired ELM-compatible BLE. Classic SPP and bonding-required adapters are not supported in this initial provider. ViaBecs ASIN B0CCYKZ8YF advertises Bluetooth LE but does not publish GATT identifiers; the owned adapter is not hardware-verified. Set up while parked; do not interact while driving. The app is informational, not a vehicle-instrument replacement.

## Evidence and limits

Tests use the actual C app/native scene with simulated serial/vehicle data and actual NimBLE with independent HCI/ATT peers. Protocol fragmentation, masks, 16 decoders, invalid/late replies, stale values, pause/resume, disconnect, ownership loss and handoff are covered.

The packager runs production strict ELF import/role admission for43 internal modules and17 SD apps, missing-import negatives for both new modules, and .86-to-.87 plus .87-to-.87 full cohorts in normal and ASan/UBSan modes. test_obd_catalog.py executes the real installed-app transaction with the exact store: dry-run/commit, foreground lifecycle, selected BLE grant, idempotence and path/grant rejection. It supplies only a simulated active invocation; no target instructions or physical I/O execute.

Independent mkspiffs readbacks, deterministic store reproduction, paired SHA/CRC, unchanged flash ranges and final BIN/SD ZIP readback are checked. Native ELF is unavailable; complete public resolver tables are observed in the exact .86 BIN and matched to source, without inventing an ELF. Host checks and framebuffer samples are not physical vehicle measurements. Exact owned-adapter compatibility and hardware testing remain pending.
