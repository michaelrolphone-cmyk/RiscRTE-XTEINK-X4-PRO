# RF Waterfall shared text input 0.3.4

This independent component recipe starts from the published Files shared-input
product `6bf5abdf8508f20c1394cc2552a28f1990b73cff`, over the qualified .102 evening
candidate. It preserves all installed apps, Files 1.5.34, scene 0.4.4, text-input
0.1.5, immutable SD host selections and the native Runtime 0.2.28 firmware.

## Exact prior source

The selected X4 RF 0.3.3 ELF is 276,932 bytes, SHA-256
`8dc03063f3c21d55ebba7fb4428363819f60b52a127e1c8b7a56e3d57405dd11`.
Its published Utilities source is `c12781b2d4e08772d06078bfff7441276cb5a7a8`,
System `c2889adff2a06bcd6c6207f11fbd0795fbbd99fa`, and Runtime
`1c1ed8661ea30d47e7e9707c41d492ce3a2b4d70`. The predecessor `build.json`
binds the exact source closure, generated SDK, full catalog, flags and compiler
command. The Watch 0.3.3 package has different source/bytes and must not be used
as this baseline. The X4 operation-scoped storage helper and all thirteen RF
model/format headers are hash-checked against c12781b2.

The new RF app adapter uses published System
`7fb13b09b4dac275a8111b224784f8a472f39264`, while the packaged scene/text hosts
remain the Files cohort's exact e3fd26c2 builds. The caller supplies the explicit
clean new Utilities commit. No unpublished SD source is exported or compiled.
The generic opt-out app stays at 0.3.3. Only this selected manifest is 0.3.4.

All original RF feature flags remain: paper preferences, resident shell/policy,
raster snapshot, native time toolbar, navigation, 90-degree rotation, full frames,
continuous radio capture, Contexts RADIO mask, BLE foreground/broadcast,
RF key-value instance 8, app-data instance 3, Home default.elf and return
springboard.elf. Shared text-client, checked-storage and custody/cleanup flags
are additive. The original complete icon/text/paper/settings fonts are checked
by hash; no font subset is selected.

## Reproduction

Use pinned Xtensa GCC 8.4.0 esp-2021r2-patch5 as `NATIVE_APP_CC`, with pyelftools
0.32 on `PYTHONPATH`. The frozen predecessor record's sibling catalog and
sdk/include are required and verified. New shared System policy headers replace
only their corresponding generated SDK inputs. The builder records all actual
compiled dependencies, source pins, command and ELF/manifest digests. Output
folders must be new. `W_TOOLS` is the published Watch tooling checkout and `W`
is frozen Watch profile 089868395268b696c05651c33816345bfe0425df.

```sh
python minimal/scripts/build_rf_shared_input.py --device x4 \
  --system "$SYSTEM_7FB13B09" --utilities "$U" --utilities-commit "$U_SHA" \
  --runtime "$RUNTIME_1C1ED866" --watch-profile "$W" --watch-tools "$W_TOOLS" \
  --baseline "$FILES_CANDIDATE" --predecessor-record "$RF_STARTUP_BUILD_JSON" \
  --output "$RF_BUILD"
python minimal/scripts/compose_rf_shared_input.py \
  --baseline "$FILES_CANDIDATE" --rf-build "$RF_BUILD" \
  --runtime "$RUNTIME_1C1ED866" --tools "$W_TOOLS" --output "$RF_CANDIDATE"
python minimal/scripts/qualify_evening_102.py \
  --runtime "$RUNTIME_1C1ED866" --tools "$W_TOOLS" \
  --delivery "$RF_CANDIDATE" --output "$RF_QUALIFICATION"
python minimal/test/rf_shared_input_recipe_test.py
```

The assembler validates the exact baseline image/store/SD/components, preserves
all 106 internal paths and 90 SD paths, and verifies startup packing order and a
minimum two-block SPIFFS reserve. Only internal waterfall.json, boot.json and
cohort.json, plus SD Apps/waterfall/waterfall.elf and manifest.json, change. The
sole authority delta is RF ui.text-input@1 instance 0. All other selected SD
images and internal fallbacks are byte-identical. The cumulative SD ZIP retains
its fourteen member paths. Native firmware and all non-bootfs/bank partitions
remain byte-identical. The full image is reconstructed only in memory by default; --materialize-full
explicitly writes the full-initial BIN, which erases internal data if flashed.

`qualify_evening_102.py` checks every one of the 43 internal and 48 selected SD
ELFs plus complete-cohort admission and OBD/Hollow native catalog contracts in
normal and ASan/UBSan builds. Those host tests do not execute Xtensa instructions
or establish physical RF/SD/navigation/resume behavior. No flashing occurs;
delivery stays held until 2026-10-12 23:30 UTC. Reapply this exact component delta
to newer authorized union work and repeat complete-cohort admission rather than
replacing newer or paused work with this independent baseline.

Explicit Home uses PORTABLE_APP_HOME_GUARD to cancel uncommitted editor and
learning/capture state, then exit after verified cleanup. Saved records and
ordinary local Back semantics remain unchanged.
