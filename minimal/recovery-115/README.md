# X4 .115 T057 test composition

Starts with the exact delivered .114 image. Keeps native Runtime, Home clock
reconciliation, RTC/alarm/sleep fixes and working OBD 0.2.2 byte-identical.
Updates only OBDTest's manifest and scene-host 0.4.7, its hashed SD image binding,
and cohort metadata. The cumulative SD overlay retains .114's six files and
adds the original OBD 0.2.2, OBDTest 0.2.4 and paired scene image. Existing SD
files and settings must be kept; neither app's settings are included.

New app features and limitations are documented in Utilities docs/t057. Scene
source and exact-font recovery are documented in System docs/t057. This is a
software-qualified test composition, not physical vehicle/display acceptance.
CSV timestamps are milliseconds since recording start, not RTC wall time.

The full 16 MiB image flashes at 0x0 and erases internal user data. It is not a
preserving OTA update. Back up settings before any separately authorized flash.
The OBDTest-only SD update can run on .114, but landscape requires the new scene
provider and matching firmware binding. No device was flashed by this work.

Reproduction: run assemble.py --help for source/artifact paths; use the supplied
.114 baseline and cumulative SD zip, recovered original OBD directory, qualified
OBDTest and scene target directories, pinned Runtime and T-Watch packer sources.
Run verify.py with --runtime, --x4, --output, --fixtures (recovery-107/fixtures),
--native-proof (its native-resolver-105.json), --baseline-store (extracted .114),
and --mode normal or undefined/asan. Assembly reproduces the baseline pack first,
packs the result twice, compares decoded contents and preserves non-store ranges.
