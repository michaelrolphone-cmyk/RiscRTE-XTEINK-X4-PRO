# Daily Paper 0.1.0

App source: `michaelrolphone-cmyk/RiscRTE-Productivity`, branch `feat/daily-digest`, commit `ba486e56dbf145a9c05d5bb36b39d9b81e0b7ece`.
Build: https://github.com/michaelrolphone-cmyk/RiscRTE-Productivity/actions/runs/38110465288
Artifact: `daily-paper-x4-0.1.0` (compiled ELF, manifest, HTTPS provider and test evidence).

The 27,656-byte ELF uses the current capabilities and reusable scene components. Launch it to fetch the latest issue from Daily-Digest-Epub, write `/Books/Daily Digest/YYYY-MM-DD.epub` and hand that source to `ebook-reader`. It has activity/progress, Cancel, and error/Retry/Close. It does not browse the archive or calculate publication checksums. Normal Reader return exits the caller, avoiding a reopen loop.

## SD and internal registration

Merge `Apps/daily-digest/` from the artifact into the existing SD root. Do not replace the Reader, fonts, books or application state. `firmware-integration/` contains internal-store build inputs, not files which become active by copying them to SD.

Current X4 Runtime 0.2.5 keeps app policy and launcher registration internal. This source change adds the Daily Paper catalog row and the additive integration recipe. A new firmware assembly is still required before an unchanged X4 build can discover/launch this app. This PR does not claim an assembled new firmware image or hardware execution. The prior 0.1.76 Reader image remains unchanged.

Stage the actual current internal store and the unpacked Daily Paper artifact:

```sh
python minimal/scripts/integrate_daily_digest.py \
  --store path/to/current/store --package path/to/unpacked-daily-paper \
  --output path/to/new-staging
```

The script adds `daily_digest.json`, `net-http-client/manifest.json`, `net-http-client/driver.elf`, the seven app grants and the foreground registration. It emits the SD executable separately. Existing store bytes stay unchanged except boot.json and these new files. The runtime provider wraps the existing `platform.http-client@1` as app-facing `net.http-client@1`; normal certificate/hostname checks remain enabled.

Rebuild Home and Springboard using the resulting catalog, retaining the current build flags, runtime/SDK inputs, display selection and resident behavior. Include those binaries in the store, advance the assembled product/cohort identity, run normal native/cohort admission and paired-bank packaging. Do not use the previous 24-app SDK Runtime as the native assembler: the deployed 0.2.5 native source is `michaelrolphone-cmyk/RiscRTE@7071f0c25e223f24670bed409a5f8b6f291c8042` with 28 app/provider slots. The addition takes the current 25-app/27-provider cohort to 26/28 without changing native limits.

The app SDK uses Runtime `536e01a36461d2e66bdfa735186c1d02267b3fb7` and System `8ddd9bcf751cecfcf74a67c50c809b87ec75fcc3`; these are SDK source pins, not a request to downgrade the native firmware. The 0.1.76 Reader 0.1.6, scene 0.3.5 and panel 0.1.12 work remains in this branch ancestry.

Tests: `python minimal/test/test_daily_digest_integration.py`. The app workflow separately runs actual app-entry success/error/cleanup tests, ASan/UBSan, target compilation, import/export checking, a 1536-byte frame limit and the production structural ELF validator. No physical download or display timing is claimed.
