# Timecard shared text input integration

Selected Timecard versions: Watch 0.2.13, X4 0.2.16. The recipe changes only
Timecard ELF/manifest, its `ui.text-input@1` instance 0 grant, and cohort metadata.
All other apps, fonts, shared hosts, native firmware, and partitions are held
byte-identical. Original feature profiles are independently pinned per device.

This branch is an integration recipe, not a firmware release. The selected clean application source is
[Productivity 395c48de](https://github.com/michaelrolphone-cmyk/RiscRTE-Productivity/commit/395c48de8fa10b672816c89c02dd9a5d4987a094).
Published-source receipts are recorded separately after reconstruction. Outputs
are held until 2026-10-12 23:30 UTC. No flashing or hardware validation occurs.
No unpublished SD-settings work is consumed or exported.

The full-initial image digest is streamed without allocating or writing a full
image. Any later full-initial flash erases internal saved data. Preserve a
minimum of two free SPIFFS blocks; no features or fonts may be removed to fit.

Read `baseline-profile.json` for the exact selected predecessor evidence. The
X4 compiler command is explicitly reconstructed from the recovered .55 profile
and the .62 raster-snapshot opt-in; the actual .62 compiler receipt is absent.
The .62 ELF itself is byte-identical to the selected current Timecard ELF.

The preliminary candidate retains 128 free SPIFFS blocks. Its Timecard ELF is
175,412 bytes. Normal and ASan/UBSan admission cover 43 internal and 48 selected
SD ELFs plus the exact OBD/Hollow catalog contracts. 103 of 106 internal paths
and 88 of 90 SD paths remain byte-identical. The cumulative changed-SD ZIP has
16 files. Final published-source receipts supersede preliminary measurements.

System Apps remains pinned to `7fb13b09b4dac275a8111b224784f8a472f39264`.
The Watch display-specialization and compiler-layout experiments are not selected.
`inspect_timecard_target_stack.py` records actual Xtensa entry-frame operands and
static modal-state ownership. It does not claim dynamic call-chain stack peaks.
