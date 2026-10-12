# X4 0.1.99: HTTPS and Hollow Trail memory repairs

This composition descends from frozen OBD .98 at
`922ac6b490fb6d3b22f642106bb1edd522c6ff4b`, preserving its OBD 0.2.1, BLE serial
0.1.0, scene 0.4.1, Files 1.5.31 and Home 0.4.13 components. Boot authority,
installation policy, all thirteen .96 lifecycle manifests, wake behavior and
filesystem placement algorithm remain unchanged.

Runtime 0.2.28 at `1c1ed8661ea30d47e7e9707c41d492ce3a2b4d70` ports only the
qualified HTTPS memory changes onto delivered native 0.2.24. Ordinary mbedTLS
allocations use PSRAM; the SDK's hardware-crypto DMA allocations remain internal.
TLS verification and connection-owned failure/cleanup rules remain enabled.
The single-job native link uses the existing X4 feature options. Static internal
RAM remains 72,464 bytes. The target compiler independently confirms both
16,717-byte TLS record buffers and the 2,592-byte ESP-TLS native handle.

Hollow Trail 1.2.2 comes from Utilities
`5c91c3517aa9f992e24fc453855701ec5a992355`. Rebuilding against the exact new
Runtime and frozen System sources reproduces ELF SHA256
`465d71581bb7655b9e2ec5de5c94b09a8fb3375f916c148497b15b431bdbfdbb`.
Sharing an inactive scenery bank eliminates one 518,415-byte startup allocation.
App-owned peak falls from 4,361,179 to 3,842,764 bytes without changing pixels,
chapters, camera modes, cutscenes, journal, controls or full-resolution rendering.
The deterministic 4 MiB allocator fixture is not a device free-memory measurement.

## Qualification and reproduction

`memory-099-inputs.json` binds source trees, the native candidate and the Hollow
build closure. `compose_memory_099.py` verifies the exact .98 baseline, every
component digest, unchanged boot policy, all unaffected internal/SD files and
unrelated flash ranges. It checks deterministic boot-order packing, full SPIFFS
readback and bank authentication. The paired manifest and SD image remain exact.

Run `minimal/test/memory_099_composition_test.py` with the .98 baseline folder,
qualified native and Hollow output folders, assembly tools and Runtime source.
Final qualification also admits every internal and selected SD ELF using the
new native resolver, validates the complete cohort and native installed catalog,
and replays the actual boot filesystem read order under normal and sanitized
host builds. Receipts identify the exact product source and image being checked.

## Installation and limits

The full-initial BIN is 16 MiB and erases internal settings, saved networks and
app data when installed as a full image. Its six-file SD overlay is cumulative
from the previously delivered .96: four OBD .98 additions and two Hollow
replacements. It assumes the SD card already contains the .96 lifecycle overlay.

No device was flashed. Host tests and target admission do not establish actual
Daily Paper HTTPS success, Hollow gameplay, heap margin, adapter compatibility
or wake timing on hardware.
