# X4 0.1.80 — Wi-Fi persistence and bounded USB batching

This coordinated increment starts from the exact delivered 0.1.79 image,
SHA-256 `8e42978eb7d7196d80bc6bbb61178ff5169e99e288c84b5f16a78c2c03ed8420`.
Remote product versions were checked before reserving the unused 0.1.80 label.

Selected completed source inputs:

- Wi-Fi 1.1.26: System `600e56bc08962c0473735b2fd5d5d80aa62b77a8`,
  X4 qualification `100acac8ed9e972fabcbe4dc578698455f06df11`.
  Preserves the resident scan fix and saves submitted credentials after successful
  association, supports multiple profiles and visible persistence errors/retry.
  Namespace 6 and existing storage authority remain unchanged.
- USB MSC 0.1.7: Reader `5fe5caa4cd7c8ab03d00e5e8e17cbac16053f743`.
- X4 SD 0.2.16: X4 `3c23b8bd2a1073bd1e3db48d6e9ae034613372c0`;
  batching qualification `2184c304a4df2011012afe7a7d01066f243b5d3a`.
  MSC and SD cooperate in bounded batches of at most eight whole sectors.
  The 2 MiB host fixture reduces endpoint submissions and native SDMMC calls
  eightfold. This is a synthetic call-count result, not measured hardware speed.

The recipe `minimal/scripts/package_wifi_usb_080.py` changes the Wi-Fi ELF and
manifest, MSC ELF and manifest, SD ELF and manifest, and cohort identity only.
All other 88 internal files remain byte-identical. It preserves native Runtime
0.2.5, panel x4pro-uc8279-fast 0.1.12, Reader 0.1.8, Scene 0.3.6,
Daily Paper 0.1.0, Home 0.4.8, Springboard 1.7.31 and Hollow Trail 1.2.1.
It does not include unfinished icon work or dynamic package discovery.

## Install

The output is a full 16 MiB image for address **0x0**. Flashing it overwrites
internal settings, NVS, bonds and AppData; back up needed data first. There is
no preserving OTA support. No hardware operation is performed by this recipe.

The matching 16-app SD ZIP remains byte-identical to the delivered .78/.79
`X4-0.1.78-Reader-Daily-Paper-SD.zip`, SHA-256
`b7e504f16d717df839f974f0dde6e5f33cf9ff303e49fbb7936784447298d2e8`.
A complete .78/.79 SD card needs no app changes. Otherwise merge `Apps/` and
`fonts/` into the SD root while apps are closed, preserving unrelated contents.
Reader remains 0.1.8. All three updated components are internal.

## Qualification and limits

Immutable source and SDK hashes, package entries and provider relocation maps
are checked before composition. The exact 54 embedded/SD modules undergo normal
and full UBSan production admission, wrong-role and unsafe-operation rejection,
and missing-import rejection for the three changed modules. Three cohort cases
exercise the installed baseline, transition and final state without hardware or
storage calls. Deterministic packing, independent C SPIFFS readback, native and
panel identity, partition MD5, ESP integrity, paired-bank SHA/CRC and final image
readback are required before emission.

Component target builds and synthetic correctness regressions are preserved as
prior evidence. This recipe reuses their exact qualified target binaries.
Hardware credential persistence/reboot, Wi-Fi behavior, Windows throughput and
safe removal, real SD timing/remount and CDC re-enumeration remain untested.
No new ASan run or target instruction execution is claimed. The owner pump cannot
preempt synchronous native SD I/O. No merge or hardware flash is performed.
