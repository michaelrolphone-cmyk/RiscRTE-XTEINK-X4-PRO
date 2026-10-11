# X4 0.1.77 — Daily Paper

Daily Paper is registered in the firmware's internal app policy, foreground list and rebuilt Home/Springboard catalogs. Its small `net-http-client` provider is installed internally. The SD application downloads the latest newspaper into `/Books/Daily Digest/YYYY-MM-DD.epub`, then hands that file to the existing Reader. There is no archive browser or newspaper checksum calculation.

The full-flash assembly uses the exact completed 0.1.76 native firmware and panel 0.1.12, preserving scene 0.3.5 and unrelated modules. It adds Daily Paper 0.1.0 and updates the Reader manifest/SD application to the completed 0.1.7 page-turn fix. Home is 0.4.8 and Springboard 1.7.31, with their existing capability requirements and behavior flags retained. There are 26 registered apps, 28 provider instances and 24 launcher entries.

## Install

Use the complete `X4-0.1.77-Daily-Paper-Panel-0.1.12-full-0x0.bin` at flash address **0x0**. Merge the companion SD ZIP's `Apps/` directory into the SD root, replacing matching files but leaving other directories intact:

```text
Apps/daily-digest/daily_digest.elf
Apps/daily-digest/manifest.json
Apps/ebook-reader/ebook_reader.elf
Apps/ebook-reader/manifest.json
```

The two JSON files are included. Do not put the HTTPS provider onto SD; this firmware includes it. Existing SD fonts, books, bookmarks and other applications are not distributed or removed by the addon.

**This is a full-flash installation, not a preserving OTA package. Writing the full 16 MiB image overwrites internal settings/data; save anything needed beforehand.** Configure saved Wi-Fi and correct date/time in Settings after installation as needed. HTTPS uses the normal hostname/certificate checks. Launch Daily Paper from the springboard. Previous dates stay on SD; repeated downloads replace only the same date after the transfer completes.

## Reproduction

`minimal/scripts/build_daily_paper_launchers.py` builds Home and Springboard with the current feature selection and expanded catalog. It requires the existing .76 store to compare every capability requirement, the Xtensa ESP32-S3 8.4.0+2021r2-patch5 compiler, and the sources pinned in the script. Reader SDK headers and relocation normalization come from `T5S3-Reader@aac8c06d3221139084acd0cfc64f7b0ba194a97a`, read-only.

`minimal/scripts/package_daily_paper.py` accepts the completed .76 BIN, launcher output, Daily Paper artifact, Reader .1.7 ELF/manifest, Runtime checkout, verification Tools checkout and independent mkspiffs binary. Use `--help` for exact path arguments. Its `--phase` option separates preparation, normal checks, sanitizer checks and final packaging. A clean destination is required for preparation.

Inputs:

- Native Runtime: `RiscRTE@7071f0c25e223f24670bed409a5f8b6f291c8042` (0.2.5; unchanged native bytes).
- Shared System: `RiscRTE-System-Apps@8ddd9bcf751cecfcf74a67c50c809b87ec75fcc3`.
- Alarm SDK support: `RiscRTE-Utilities@e80172353fcb9e6519ca9d9b2a4d43c69c1bc91d`.
- Verification Tools: `RiscRTE-T-Watch-S3@db5f6c5ba1a71ed3fcc22ff29847397a050b7ee4`.
- Daily Paper: `RiscRTE-Productivity@ba486e56dbf145a9c05d5bb36b39d9b81e0b7ece`.
- Reader 0.1.7: `RiscRTE-Productivity@3898250decc89abe6f603021a970625b9f2538c7`.
- mkspiffs: `igrr/mkspiffs@112d65368043f01dd86813cb84e41b1159a34f6b`, built with `SPIFFS_OBJ_META_LEN=4`.
- Python ELF inspection: pyelftools 0.32.

The native symbol witness is extracted from the actual supplied firmware, cross-checked against its exact resolver source. This does not manufacture an original native ELF. Full-store policy admission uses the production Runtime and exact native ELF admission code. The baseline and final installed cohorts are tested separately; the deployed Runtime correctly rejects an in-place OTA expansion of the already-owned Wi-Fi credential namespace. That rejection is recorded rather than bypassed or presented as an approved OTA update.

Normal validation exhaustively tests missing imports of the changed modules. ASan/UBSan repeats all 40 actual module admissions, wrong-role and unsafe-operation rejection, plus representative missing imports. The packager independently unpacks baseline and output SPIFFS images and verifies every file, paired hashes/CRC and unchanged native/panel ranges. `build-custody.json` records exact outcomes and inventories. Host execution does not claim physical X4 operation or timing.
