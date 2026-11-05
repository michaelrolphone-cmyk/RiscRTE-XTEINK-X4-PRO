# Isolated Wi-Fi native build measurements

The new native-wifi-build workflow is read-only with respect to repository state. It has no release, package publication, device, format, erase or deployment step. It uses the existing official IDF6.1 image pinned by digest, verifies SDKfff9895c82d744c7237be8847347bdd1b07c6643, and clones Runtime712ecc3f894dba99d9c9638941778a82f5856b97 plus the exact product commit. LittleFS is the Runtime's pinned vendored implementation; there is no new filesystem source selection.

It first tests the production-selected registration/admission profile, then creates a fresh native-wifi build. An independent fresh build of the unchanged native-provision-123 profile uses the same Runtime and product checkout for a controlled profile-selection comparison. Neither build is a recreation or certification of a historical released binary.

The producer reuses the existing controlled native build's environment isolation, exact compiler-family checks, compiler/Ninja/link-map dependency census and in-process custody token. It does not invoke the .122 or .123 packaging/qualification recipes. Product sources, existing profiles and release manifests remain unchanged.

Both builds retain actual firmware.bin, ELF, map, compile commands, SDK configuration, source/dependency closure, stack-usage files and logs. The Runtime linked-native boundary test checks actual Xtensa firmware and retained image identity. Measurements include allocated section bytes, firmware bytes, large symbols and exact stack-usage files. The comparison reports section/firmware deltas only.

No heap peak, runtime allocator overhead, task high-water mark, real storage reservation, reboot preservation or companion-store admission is established by this build. Receipts deliberately say these are not qualified and do not satisfy the System-Apps native-cohort success gate. A successful link is an implementation prerequisite, not approval to install or activate the new authority.

The workflow runs on matching pull-request paths or explicit dispatch; push triggers are omitted to avoid duplicate full builds. It retains artifacts on failure and does not continue past a failed assertion. The previous profile build runs independently after source/profile checks, even if the successor fails. If a post-link guard rejects a readable ELF, the producer records diagnostic section addresses, internal BSS symbols and allocator configuration, then rethrows the failure. Rejected measurements never become qualified firmware. The comparison records each build status and cannot turn a guard rejection into a pass.

## First measured rejection

At product7889646e, Runtime712ecc and the pinned SDK, run42008596704/job127181547300 reached final native linking. Runtime's unchanged radio_iq_proof rejected .dram0.bss overlapping the reserved IQ bank0x3FCB0000–0x3FCC0000. Artifact13405184538 (ZIP SHA256e9f48cf1ec42768880136cb7009685eb17cbc5f9cdccc7dbcd7617f264033b1a) preserves the rejected ELF/map. No placement, limits, features or IQ guard is changed by the diagnostic follow-up.
