# X4 selected native backends

The SDK6 successor preserves the released profile's TCP listener, entropy and
SDMMC selections. It retains their allocated ABI markers with linker `-u`
options so section garbage collection cannot hide the final-ELF proof. Missing,
ambiguous or altered markers are still rejected.

X4 does not select the separate `RISC_NATIVE_FILE_SOURCE` scratch backend.
`file.open` is the existing SD-volume handoff capability; `file.open.source`
is a different capability requiring `/appdata/.risc-file-source` storage.
The exact released factory and complete SD archive in `released-baseline.json`
contain zero `file.open.source` grants or requirements across all 107 internal
and 77 SD files. They retain `file.open` grants and manifests. The released
native image also lacks the scratch path and the backend's startup/retained
error strings. The checked released profile contains no file-source selection.
The historical native ELF remains unavailable; these observations do not claim
that a missing ELF was recovered.

The X4 checker now rejects a `file.open.source` capability in either immutable
payload inventory, a linked `risc_file_source_abi` or `RiscFileSource` backend,
and a compile-time file-source enablement. Its host admission fixture is
explicitly disabled for file source and requires the final native proof to
agree. This corrects an overbroad Watch/Wave-derived gate and fixture; it does
not enable a new product backend. Both selected-marker omission and accidental
scratch-backend enablement have negative controls.

Official run 38790023086 linked the unchanged IQ reservation successfully, then
stopped before candidate admission because the TCP marker had been garbage
collected. Exact failure artifact 11999948053 has SHA256
`6cbd5a00970bb56d1baac3f1370918ab765509600618dc75fef1077115891cf1`.
Its native ELF has SHA256
`6f248f448f49b85f0332d94e4c821b55ed83736d4dd2100a903e9600b552d174`.
Independent inspection found TCP and entropy markers absent, SDMMC and capacity
markers allocated in flash, and file-source absent. Final bootlog placement and
IQ proofs still pass. These are diagnostic results, not a qualified candidate;
a new controlled build is required for the corrected source checkpoint.

The released `installation.settings_sd=true` selection also requires the existing
NVS journal read/write/legacy-namespace interfaces. `NvsKeyValue.h` already
supplies them in the selected native Runtime. The product host fixture now
models their presence using counted failure callbacks, matching the existing
get/put fixture: no persistence operation may occur during admission. All 43
released internal ELF payloads pass production-source cohort admission against
the exact CI9 ELF normally and under ASan/UBSan, with file source disabled and
zero hardware/storage calls. This diagnostic does not mint a fresh-build receipt
or turn the failed CI9 run into a qualified candidate.

The complete SD49 ELF campaign also passes against the same exact diagnostic
ELF, normally and under ASan/UBSan, including wrong role, unsafe operation and
every missing-import rejection. The 1,918,724-byte ebook-reader payload takes
9.826 seconds normally and 82.290 seconds sanitized for its full 31-import
negative campaign. The old 60-second per-process timeout was too short for
that sanitized workload. The runner now has a bounded 300-second per-ELF
limit, over 3.6 times the observed sanitized duration, and records elapsed
seconds for each payload. It still fails on timeout and retains every check.
