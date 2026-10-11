# Source checkpoint: Available networks freeze on combined X4 .78

The focused repair is System Wi-Fi **1.1.25** at
`f5673befd745a744872e4802332e647d64577a5c`, branch
`fix/wifi-resident-scan-078` in `michaelrolphone-cmyk/RiscRTE-System-Apps`.
This X4 branch is based on the exact combined `.78` receipt
`8e9e8eb7a2b1f7f860777d0d0e8a89dd2822af87`. It records source and
qualification; it does not replace a full image or advance its product version.

## Selected code and demonstrated cause

The installed internal Wi-Fi 1.1.24 app was rebuilt from System
`5b28172e979b5f008da19e9a00a3b98e35937974`. Every allocated ELF section
matches the delivered binary, including executable code, constants, relocation
and export tables, data, and BSS layout. Nonloaded stripped metadata differs.
Its async scan suffix, shared masked keyboard and saved profiles are present.
Provider 0.2.1 is Watch `a304597bf26491483bb0a567569f0ca0267cdf9c`.
The actual native is Runtime 0.2.5 at
`7071f0c25e223f24670bed409a5f8b6f291c8042`; do not select the stale native
entry in `minimal/sources.lock.json` for this delivery.

The tap starts a copied native worker operation. Once the display settles,
normal input polling enters a resident POLL checkpoint despite active radio
ownership. Runtime applies its invocation-switch exit barrier before the host
sees policy flags. CpuPort rejects exit while the radio is active, permanently
retaining the foreground. The baseline regression demonstrates the bad crossing.
The fix returns BUSY locally for this checkpoint while Wi-Fi async ownership
remains, keeps input/render/cancellation scheduling alive, and resumes host
polling after checked quiescence. No native locks, callbacks, worker lifetime,
cleanup guarantees, renderer pipeline or Runtime barrier are weakened.

## Exact component recipe

Use the fixed System checkout above; Runtime checkout at the selected native
commit; Utilities at `e80172353fcb9e6519ca9d9b2a4d43c69c1bc91d`.
Export `sdk/app` from Runtime commit
`274bc66f193cbe29018d2a85c9400cb0dce8aacc` into a separate SDK directory.
This is the historical component-header selection, not a downgrade of native.
Use GCC 8.4.0 `esp-2021r2-patch5` through `NATIVE_APP_CC`.

```
python3 System/scripts/build_portable_wifi.py \
  --resident-shell-client --resident-runtime-sdk SDK/sdk/app \
  --resident-policy --alarm-client --home-app default.elf \
  --tagged-alarm-utilities Utilities --native-time-runtime-repo Runtime \
  --touch-scrolling --ble-broadcast --navigation --time-profile x4-native-time \
  --stage-logs --wifi-instance 15 --return-app springboard.elf \
  --raster-snapshot --output-dir build/wifi-1.1.25
```

The clean source target compile, ELF structural validation and import/export
checks passed. Exact command, SDK hashes, source hashes and output hashes are in
`docs/evidence/wifi-resident-078/wifi_settings-build-record.json`.
The unstripped component SHA-256 is
`b54e7d6d17eae9acb9541147734f8291a53adfe1ff6c9158d7eac850c4196a8e`.
Its loaded text increases by 12 bytes; data/BSS sizes remain unchanged.

## Integration instructions

Replace only internal `wifi_settings.elf` and `wifi_settings.json` with the
paired 1.1.25 build outputs. Update the generated cohort/package hashes and
admission evidence through the existing assembler; do not edit a delivered
image in place or claim this standalone component is a qualified full image.
Wi-Fi is internal in .78, so copying this ELF to SD alone does not select it.
Keep its existing capability grants and native/provider selection.

Preserve Reader **0.1.8**, Daily Paper **0.1.0**, panel **0.1.12**, all 16 SD
apps, Scene **0.3.6**, Home **0.4.8**, Springboard **1.7.31** and every other
internal artifact from the complete .78 delivery. Do not rebuild these from the
older Wi-Fi source branch. Preserve the sliced renderer option and decoupled
input/presentation code. Combine this replacement with separately approved USB
or discovery changes only in a new explicitly versioned integration; this
checkpoint has not incorporated those active tasks.

## Verification and limits

Normal and UBSan tests pass for the production controller and resident checkpoint
with delayed scanning, copied results, setup failure, timeout, cancel/reentry,
connected ownership and retained cleanup. Input polling and rendering continue.
The actual provider/CpuPort/native worker suite passes 58 cases per mode with
the app seam, including a blocked `wifi_init`; the basic native suite passes 57.
Existing app workflows pass 56 per mode and the 50-profile fault test passes.
The checked-in receipts state synthetic SDK/peripheral/dispatch boundaries.
No RF duration, hardware recovery or actual device fix is claimed without a
hardware retest. No full-image assembly, hardware access, flash, master merge
or release was performed.
