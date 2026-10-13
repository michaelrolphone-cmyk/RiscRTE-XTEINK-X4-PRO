# X4 .110 Scanner modal policy (held candidate)

This cumulative candidate starts from the immutable .109 image SHA256
3abf377e2caef8cae728decd7697712f8c3f47fc26d4626ab110d1b51174ae46.
Only boot.json, cohort.json and ble_scanner.json change in the 107-file store.
All 43 internal ELFs, native a91 firmware, RTC/Home fixes, RF, Points, OBDTest,
text host, settings partitions and unrelated flash ranges stay identical.

Scanner 0.2.25 source was reconstructed before edits and reproduced deployed
SHA256 a21d03b37168feb9f1dd7ae1d7c7620c6d4ab67960bc65db7189d0f5a9431b8d.
The 0.2.26 successor is 2fd57fe781737b6203f7d35479152825e8c636705e0284594007c0f260c2754c
(162860 bytes). System PR113 ab388f92324c90dc892b709a5fd5870548f03e08 and
Utilities PR67 1ac4e3e177d5b6de5eb375e04ee9dd3a0002324b preserve the source
and pinned reproduction. The policy-disabled candidate reproduces .025 exactly.
This uses the deployed X4 renderer, atomic preference storage, radio behavior,
and shared editor. No older Watch binary or UI replaces it.

The editor now pauses for resident policy dispatch, resumes the same draft,
retains uncertain custody, and completes delayed close before Home return.
An exit arriving during editor polling cancels before a persistence write.
Local qualification passed 158 actual controller tests, 86 production
app/adapter/shared-host replays (normal and UBSan), and all 65 baseline frames
were unchanged. Native sleep, resident dispatcher and peripherals are boundary
fixtures; no physical device qualification is claimed. Linux ASan/UBSan CI
results are recorded separately when complete.

The SD overlay keeps all four .109 RF/Points files unchanged and adds two
Scanner files at Apps/ble_scanner/image-<ELF SHA256>/. Merge these six files into
the existing card. Existing Scanner and other SD paths remain recoverable.
The full physical card inventory has not been audited.

Assembly: run assemble.py with --baseline <109.bin> --baseline-sd <109-SD.zip>
--scanner <qualified-target-directory> --runtime <native-a91-checkout>
--spiffsgen ../recovery-107/vendor/esp-idf-spiffs/spiffsgen.py
--product-commit <published-recipe-commit> --output <new-directory>.
Run verify.py with recovery-107 fixtures and the .109 baseline store for full
production admission, normally and under UBSan. Native export addresses are
re-read from the unchanged firmware BIN.

.109 exact-head platform and typed-driver CI is green. The PR112 frozen Reader
comparison failure is inherited: unchanged 5b28172 and PR112 produce the same
portable and Reader hashes, failing the same 480x800-segments-0000-24h assertion.
The mismatch is 20,992 pixels in both; the clock-face sources are unchanged.
Evidence is retained without changing golden files or claiming a device-clock
regression from that lane.

Hold delivery until 2026-10-13 23:30 UTC. No merge, release or flash. Physical
RTC/display refresh and sleep/wake comparison, editor input/power behavior,
and application smoke tests remain. A full 16MiB image overwrites internal user
data; unchanged baseline settings bytes do not preserve live device settings.
