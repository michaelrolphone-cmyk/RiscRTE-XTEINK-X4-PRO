# X4 .96: explicit installed foreground lifecycle

The supplied device logs show SD BLE Scanner and Calculator reaching their first
frame, then retaining the invocation. Internal Battery returns normally. The SD
applications are resident clients, but their manifests omit runtime_lifecycle.
The native installed-package contract deliberately treats omission as legacy:
Home unloads, the child has role 0, and its first settled resident checkpoint cannot
bind the expected foreground host. The adapter's alarm failure wrapper retains
uncertain custody, producing the exact reported diagnostic. This is a lifecycle
metadata mismatch, not evidence of a CPU exception.

## Narrow correction

Thirteen source-bound, already selected SD foreground apps gain the existing
`runtime_lifecycle: "foreground"` field in their SD manifests and internal
authority mirrors: BLE Scanner, Points in Time, Calculator, Stopwatch, Countdown,
Timecard, BLE Touchpad, BLE Buttons, Waterfall, Contexts, Lists, Ebook Reader and
Daily Digest. Each exact delivered ELF must export the valid 16-byte role 2
resident descriptor before the recipe will produce an image. The application
identity, executable package version, entry and capability requirements are
unchanged. Only deployment metadata changes, recorded by product version .96.

Gameboy, Model Viewer and Hollow Trail remain legacy. Unknown apps are not
implicitly promoted. No grant expansion, retention relaxation, native change,
Home change, Files change, or SD executable replacement is included. Future
product qualification rejects the same missing/mismatched lifecycle metadata.

Baseline source is .95 commit 7e7b632e2625ffd3769194456a289ba60671cb04,
full BIN SHA256 f20a37e7ff99cfa29664dc2e63f33f78ffd8dffcb04bb8124e3a533dfbcb166c.
The exact baseline receipt, all 103 store paths and all 81 SD files are SHA-bound.
Internal changes are thirteen metadata files and product cohort identity only;
SD changes are exactly thirteen manifest.json files. All42 internal ELFs and
all 46 selected SD ELFs remain byte-identical. Runtime .2.24, Home .4.13, Files
1.5.30, Points, alarms, .93 minute SD-close behavior and .95 boot placement remain.

## Qualification

- One hundred negative/preservation probes cover missing/wrong lifecycle,
  mismatched mirrors, wrong ELF role, changed grants/version/name, accidental
  conversion of legacy apps, repeated repair and unrelated flash changes.
- Real production Runtime .2.24 passes 12 mechanism-level lifecycle scenarios
  normally and under ASan/UBSan: missing declaration unloads Home and enters role 0;
  explicit foreground keeps Home resident and dispatches the checkpoint; three
  real legacy identities remain legacy; missing/wrong descriptors fail closed
  before app init; removable image handles close before entry.
- Those executable fixtures are host builds, not Xtensa execution. Actual SD
  files are separately bound and their loaded descriptors checked. Physical .96
  application execution still requires the owner's device test.
- Actual-native strict ELF/import and complete metadata/cohort admission covers
  all 42 internal and46 selected SD ELF files, plus four namespace-change rejection
  probes. No hardware or storage calls occur in graph admission.
- Seven exact pinned SPIFFS plans compare every read byte normally and under
  ASan/UBSan (same packed-index alignment exception as .95). Metadata name-lookup
  reads remain 193; healthy-SD first-frame internal name reads 205; free blocks 232.
  No new claim of physical wake time is made.

See the source-bound receipts in evidence/sd-lifecycle-096. The earlier
SD_LIFECYCLE_096_WIP.md is a historical checkpoint and is superseded by this record.

## Reproduction

Run `minimal/test/sd_lifecycle_096_test.py` with --baseline (qualified .95 delivery),
--sd (unchanged complete .90 SD tree), --tools (hash-pinned shared assembly source)
and --runtime (clean .2.24 source 6377d498a47b59dac8ad85d930983fffc6c8baa5).
Set RUNTIME_REPO to that checkout and run minimal/test/sd_lifecycle_runtime/run.sh;
repeat with SANITIZE=address-undefined and ASAN_OPTIONS=detect_leaks=0.
Run compose_sd_lifecycle_096.py with --baseline, --sd, --tools, --runtime-source,
--product-revision (clean published .96 source) and a new --output. Then use the
unchanged matching native BIN/ELF with qualify_installed_catalog.py, provider
capacity 40, shared-files, generated SD tree and sd-lifecycle composition receipt.
Native/app target rebuilds are intentionally unnecessary: executable bytes are
identical to the delivered source-bound targets.

## Install

The raw 16 MiB BIN is a FULL INITIAL image at offset 0x0 and erases internal settings,
saved Wi-Fi and app data. The SD archive contains only 13 paths under Apps/.
Merge Apps/ into the card root and overwrite those manifest.json files. Do not
format the card or remove applications, books, ROMs, fonts or saved state.
Use the paired .96 BIN and SD overlay for the qualified composition.
