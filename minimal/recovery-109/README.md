# Cumulative X4 0.1.109: Points modal policy

The exact input is immutable .108 BIN SHA-256
9a55a27d0ad689295eacd248a378f54577ce2997fea51454304bdd70effae835.
Its RF overlay SHA-256 is
687ad13059b36c6f3841cf36f2eeaa7f7c0452145bf8511d91651da9b8315940.

Points 0.6.17 was reconstructed byte-for-byte from Productivity d6a9657,
System 5b28172, Runtime SDK b25b1d4 and Utilities 35c2141. The deployed ELF
SHA-256 is 0ea368123a6f07bc251e233a15f116831fd2cf60e1144e9ae0514bb231dc0501.
The reconstructed source includes the X4 semantic renderer and differs from
the older Watch selection. No Watch binary or renderer is substituted.

Qualified successor: Productivity c671a34c5617ee4e33c92603e518fbc3dcad376f,
System c4579cdb14f4ce185aed32d5de86f44a25733007, Runtime SDK a91edf3,
Utilities 35c2141. The Points 0.6.18 compact ELF SHA-256 is
cbc08f8c5846967b7c9cdc5cae4f832e2a0ec7c8a3534d565eebef804ae92a2d.
Linux workflow 38470194627 reproduces both baseline and successor exactly,
passes 49 baseline regressions and 65 candidate scenarios normally and under
ASan/UBSan, and verifies 38 full frame comparisons. The text-provider and
resident-dispatch boundaries are deterministic fixtures, not physical hardware.
Existing draft-only Done, separate Save, schedules/types, storage and grants
remain unchanged. New checkpoints permit resident policy during the shared
name editor; retention and resident/Runtime exit are explicitly fenced.

Only boot.json, cohort.json and points_in_time.json change in the internal
store. All 43 internal ELFs, native firmware, .107 Home clock fix, OBDTest,
settings ranges, RF selection, Files and text host stay byte-identical to .108.
The selected manifest retains the delivered foreground lifecycle declaration.

The cumulative SD ZIP retains .108's two RF files byte-for-byte and adds the
Points ELF and manifest under Apps/points_in_time/image-<ELF SHA-256>/.
Merge the four files into the existing card; do not replace or delete other
files. The old Points ELF and manifest remain available at their original paths.
No complete physical-card inventory was available or is claimed to be audited.

Reproduce assembly with assemble.py --baseline <108.bin> --baseline-sd
<108-SD.zip> --points <qualified-compact-ELF-and-manifest-directory> --runtime
<native-a91-checkout> --spiffsgen ../recovery-107/vendor/esp-idf-spiffs/spiffsgen.py
--product-commit <published-109-recipe-commit> --output <fresh-directory>.
Run verify.py using recovery-107 fixtures and the .108 baseline store for
production loader and complete cohort admission, normally and under UBSan.
Assembly verifies baseline SPIFFS reproduction, boot grants, flash ranges,
paired bank hashes, deterministic packing and readback.

The broad historical Productivity unit suite has pre-existing failures in
historical Git-file lookups and stale Timecard version expectations. They also
occur on the unchanged deployed Points source; the reproduction log is kept
beside successful focused qualification. No Timecard or Scanner code is changed.

Delivery is held until 2026-10-13 23:30 UTC. Physical editor, input, power,
sleep/wake, and RTC/Home regression checks remain. No merge, release or flash.
Flashing the full 16 MiB image overwrites internal user data; identical baseline
settings bytes do not preserve the live device's current settings.
