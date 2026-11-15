# Unpublished X4 Wi-Fi policy successor

This source candidate preserves the frozen native-idf61 and native-provision-123
profiles and their six-writer settings header. It changes no release manifest,
firmware image, boot store, app grant, partition, existing data or device.

profiles/native-wifi.cmake is a separate successor of the .123 configuration.
It keeps the same partitions, mount fences, source-discovery settings, namespace
mask, logical owner, volume instance and existing six writers. It enables the
existing preferences broker and selects native-wifi-settings.h, appending only
wifi_settings in namespace1. Seven writers plus two read-through entries require
nine Runtime atomic binding rows; the successor declares those actual capacities.

The former Wi-Fi policy already holds KV1 namespace1 authority. The candidate
preferences1 grant is not installed here. Native registration alone does not
grant application access. Matching app declarations, exact namespace grant,
source-bound firmware selection and full product admission remain required.

The application must use storage.preferences@1 for its single four-byte
quick_radio record. Legacy Watch/Wave backends may offer COPIED_INPUT without
ATOMIC_GROUP. This X4 selection uses its existing native endpoint. The facade
must never downgrade an unregistered native-namespace writer to legacy storage.
Saved-network multi-key updates still require atomic namespace6.

Run the focused profile/Runtime test with:
    python3 minimal/test/native_wifi_profile_test.py --runtime Runtime --output evidence/wifi-policy

The script pins Runtime712ecc3f894dba99d9c9638941778a82f5856b97, configures both
old and new real product profiles, checks only the intended definition/header
selection change, and derives broker flags from the successor. It compiles actual
Runtime with the source-owned product writer header in normal and sanitizer modes.
The native endpoint disk and payload are host fixtures. It checks old writer-set
refusal, exact ninth binding admission, preservation of the previous eight
bindings, foreign-app refusal and zero native-storage callbacks during admission.

This focused test is not full target firmware qualification, real installed ELF
admission, capacity/stack proof, radio behavior, or hardware validation. No test
has been claimed passed before CI execution. Next qualification must link the
actual successor firmware, measure the extra Runtime/native control allocation,
run all existing native storage/custody/reboot regressions, and assemble the
preserving product candidate against its exact native selection. Do not alter
old profile tests or use the newer fixture to certify unchanged old firmware.

Watch namespace6 migration and shared AppData replacement-reservation work remain
separate prerequisites; this X4 registration does not establish their safety.
