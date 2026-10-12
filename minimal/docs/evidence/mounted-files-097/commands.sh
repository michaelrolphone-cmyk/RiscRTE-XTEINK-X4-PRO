#!/usr/bin/env bash
# Recorded local verification commands. No publication or device operations.
set -euo pipefail
cd /workspace/shared/x4-mounted-files-097-20261012
export PYTHONPATH=/tmp/x4-keyboard-091-python
BASE=/workspace/shared/x4-lifecycle-096-delivery
FILES=/workspace/shared/files-mounted-target-preflight/x4-cbf8c5d
SYSTEM=/workspace/shared/files-mounted-browser-20261012
TOOLS=/workspace/shared/watch-mounted-files-1116
RUNTIME=/workspace/shared/x4-fast-native-20261012
OUT=/workspace/shared/x4-mounted-files-097-preflight
EVIDENCE=/workspace/shared/x4-mounted-files-097-evidence
ADMISSION=/workspace/shared/x4-mounted-files-097-preflight-admission
# Outputs already exist. For replay, use new output directories and the clean
# recipe source a327b4e320f40ece1c1b3852e55b21882f04ca16 in its own worktree.
python3 minimal/test/mounted_files_097_test.py --baseline "$BASE" --files "$FILES" --system-source "$SYSTEM" --tools "$TOOLS" --runtime-source "$RUNTIME"
python3 minimal/scripts/compose_mounted_files_097.py --baseline "$BASE" --files "$FILES" --system-source "$SYSTEM" --tools "$TOOLS" --runtime-source "$RUNTIME" --product-revision a327b4e320f40ece1c1b3852e55b21882f04ca16 --preflight-only --output "$OUT"
python3 minimal/scripts/verify_mounted_files_097.py --baseline "$BASE" --output "$OUT" --tools "$TOOLS" --runtime-source "$RUNTIME"
python3 minimal/scripts/qualify_installed_catalog.py --runtime "$RUNTIME" --tools "$TOOLS" --native-bin "$OUT/components/firmware.bin" --native-elf /workspace/shared/x4-fast-native-build-20261012/.pio/build/esp32s3-16mb-appdata-iq-stage/firmware.elf --store "$OUT/store" --sd "$OUT/SD" --composition-receipt "$OUT/receipts/mounted-files-composition.json" --provider-capacity 40 --shared-files --output "$ADMISSION"
SPIFFS=/workspace/shared/watch-spiffs-profile-20261012
cc -O2 -I"$SPIFFS/shim" -I"$SPIFFS/src" minimal/test/spiffs_boot_order_replay.c "$SPIFFS"/src/*.c -o "$EVIDENCE/spiffs-replay"
cc -O1 -g -fsanitize=address,undefined -fno-sanitize=alignment -I"$SPIFFS/shim" -I"$SPIFFS/src" minimal/test/spiffs_boot_order_replay.c "$SPIFFS"/src/*.c -o "$EVIDENCE/spiffs-replay-asan"
for PLAN in metadata fallback cold-sd healthy-sd all-files timer-fallback random-all-files; do
  for MODE in '' -asan; do
    ASAN_OPTIONS=detect_leaks=0 "$EVIDENCE/spiffs-replay$MODE" "$OUT/components/bootfs.bin" "/workspace/shared/x4-layout-proof-20261012/$PLAN-plan.txt" 4 fstat "$OUT/store" > "$EVIDENCE/$PLAN$MODE.csv"
  done
  cmp "$EVIDENCE/$PLAN.csv" "$EVIDENCE/$PLAN-asan.csv"
done
