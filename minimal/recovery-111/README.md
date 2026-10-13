# X4 .111 Wi-Fi modal policy candidate

Starts from immutable .110 BIN c01c7fe4dacb80a1d2ae458fcc8f5bb176e3dc6bfa8ddb0621acb60a4944fd18.
Only wifi_settings.elf, wifi_settings.json and cohort.json change. Boot authority,
.105 Home/boot fixes, .106 OBDTest registration, .107 RTC reconciliation, all 42
other internal ELFs, native Runtime a91 and settings flash ranges remain identical.
The complete .110 RF/Points/Scanner six-file SD ZIP is copied byte-for-byte.

Wi-Fi source is published in System PR114. Recovered source checkpoint 8f6670a
reproduces every deployed 1.1.28 ELF section except four compiler-generated .strtab
symbol names. The successor retains the bounded Runtime table extent correction,
password masking, shared keyboard, scan/connect, multiple saved networks, atomic
namespace 6, availability and explicit draft-discard requirements. Modal policy
only runs at settled checkpoints with host pause/resume; active radio/storage
work inhibits sleep. Home/runtime exit cannot save an unaccepted edit.

Run assemble.py with --baseline <110.bin> --baseline-sd <110-SD.zip> --wifi
<qualified-target-directory> --runtime <native-a91-checkout> --spiffsgen
../recovery-107/vendor/esp-idf-spiffs/spiffsgen.py --product-commit <recipe-commit>
--output <new-directory>. verify.py uses recovery-107 fixtures/native proof and
.110 store. It checks every ELF against exports read from unchanged native bytes,
then admits the complete store with production Runtime and CpuPort, without I/O.

Hold user build delivery until 2026-10-13 23:30 UTC. No merge or flash. Physical
RTC/display refresh and sleep/wake comparisons, modal low-battery/idle behavior,
Wi-Fi networking and application smoke tests still require the device. Full
16MiB flashing overwrites internal user data; preserve existing SD contents.
