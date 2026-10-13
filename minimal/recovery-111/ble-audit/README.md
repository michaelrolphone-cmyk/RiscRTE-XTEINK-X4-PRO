# Selected X4 BLE reconciliation — 2026-10-13

No surviving BLE defect was reproduced. No production source, version, .111
image, Library item, or .110 fallback was changed by this audit.

The retained .90 SD overlay contains Buttons 0.1.25 (SHA256
`91497b0f2dd97e307258dbd50128a7f7e94d444c3711f7db0b9fe82e024289c4`)
and Touchpad 0.1.23 (`4138f2364aca210d02a81dc7427c1665fa1ba89af1c76650b39e851b704550ec`).
Both reproduce byte-for-byte using the original resident/raster flags,
Utilities b7b3e879791ddf61a4e20b1ba123da9a13835045 and System
5b28172e979b5f008da19e9a00a3b98e35937974. Their shared HID app/model/gesture
source is unchanged from the qualified queued-tap source e620160. Version
increments through .25/.23 were shared renderer changes, not a loss of that fix.

HID 0.1.4 reproduces byte-for-byte from Drivers
58ad37140bd86bd2247bfa3244c4acc8942b2bd8 using GCC 8.4.0 esp-2021r2-patch5
and the existing loader-metadata-v3 compactor. The resulting 125480-byte ELF
SHA256 `6290d9cdfae051b9f2f2c83060f1c4000a62f727d47b680c67cd77b0d9e0c555`
matches both the retained SD copy and .111's internal fallback.

## Fresh checks

- 26 actual GT911 0.1.10 + selected Buttons app/adapter command cases pass
  normally and under UBSan, with the existing asynchronous-display fixture.
  This includes queued/sampled/configured/rapid keyboard and mouse commands,
  exact neutral reports, unsafe timing/contact/security/generation rejection,
  queue gaps, disconnect and failed-report cleanup.
- All 34 production NimBLE protocol cases pass normally, including saved-LTK
  reconnect, mouse reconnect, transport recovery, backpressure, Forget/new host,
  lost disconnect, terminate race, retained cleanup and reboot.
- Twelve model, gesture, Buttons/Touchpad controller and resident capture-gate
  runs pass (six normally and six under UBSan). Advertising and comparison stay
  active; timeout/reject/error release policy only after checked cleanup.
- Production provider NPL FIFO/timer wrap/cancel, locks, arena and queue tests pass.

Five cases fail under the old synchronous fixture, which advances its synthetic
clock by 1600 ms during submission and injects a resident idle jump. This is not
the selected UC8279 asynchronous-present contract. Its existing
`--asynchronous-display` mode keeps a pending token while input continues;
all 26 assertions then pass. Assertions, not process completion alone, were
checked. Only fixture compatibility was adapted: its duplicate alarm-output
typedef was removed because the recovered SDK already supplies it. Production
app, adapter and GT911 sources were not altered.

macOS's signed Python rejects ASan/UBSan runtime loading for the ctypes protocol
fixture. These attempted runs are not passes. No platform security setting was
changed. Native executable UBSan command/controller coverage passed.

## Reproduction and custody

The scripts here are task-workspace audit helpers: copy them to an
`x4-ble-audit/` directory beneath a workspace containing the named checkouts.
`receipt.json` records their selected input hashes and build flags. Restore the
original target SDK from Library item
`libfile_2146df10075c8191b1cd634780710d4c` (BLE Buttons .22 source/proof), then
overlay the selected System PortableApps headers as `rebuild-apps.py` does.
Retained artifact: Library `libfile_43a985db9a1c8191aac99e11c994e3c4` (.90 SD).
Its matching receipt is in `libfile_5682a210ac9c8191bfefc65cc5b1d70f`.
The later .103 and .111 changed SD overlays contain no BLE app replacement.
Run `run-command-matrix.py` with `--asynchronous-display`, the reconstructed
receipt, SDK, selected System and current X4 minimal GT911 source/fixture;
add `--sanitize` and `AUDIT_UBSAN_ONLY=1` for the UBSan run. Set PATH to the
audit `bin/cc` symlink targeting `host-cc.py` on macOS. Linker-only portability
translations preserve production source. `run-controller-tests.py` and
`run-hid-protocol.py` record every result rather than stopping at the first case.

No physical device/card was read or flashed. Actual installed SD bytes,
over-air host command acceptance, bonded PC/phone reconnect after sleep/wake,
Forget/re-pair, coexistence, latency and power remain hardware checks.

## Separate inherited CI distinction

System PR113 head ab388f9 / run 38474221805 failed when the newer PR-base
workflow called `scripts/test_file_browser_appdata_export.py` after file-operation
tests. The workflow checks out the PR head. That head and its historical
component base 5b28172 both omit the script and have the same workflow blob
ad568d15a1595e3e87f24f73180670c15975dc51, which does not call it. The PR base
b3e11dae has both the script and newer workflow
4f8a0fec10cf43c167fcb5448b48c360a8e3ba58. Scanner's patch changes neither.
This is an inherited component/workflow mismatch, separate from the previously
recorded Reader comparison failures. Current Wi-Fi qualification 38478290352
and .111 final platform/driver checks remain green; they are not evidence that
this older broad run passed.
