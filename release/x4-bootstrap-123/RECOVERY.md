# Archived-byte qualification publication

The release source remains the original compiled product revision. A later
qualification source and run may qualify its unchanged archived native and
package bytes. This path is explicitly selected by `qualification_recovery` in
the finalized transport contract; the legacy successful same-process path keeps
its existing requirements.

The recovery contract pins both exact run attempts, jobs, workflow hashes,
source commits/trees, original full reproducibility artifact, original bounded
qualification artifact, recovered candidate/qualification artifacts, and bounded
admission-input artifact. The original producer must have failed only its
combined qualification step after producing the archived build. The recovery
run must pass every required source, custody, host-control, admission, evidence
staging and upload step. Extraction-only success cannot authorize publication.

The publisher independently retrieves both official run histories and source
trees. Only the explicit qualification/workflow/docs/test paths may differ, and
every changed file's SHA-256 and Git blob SHA must match the receipt and official
source. Native and package producer inputs cannot change in this mode.

The raw original source lock, build closure and package receipt remain intact.
Their inventory entries bind the exact preserved bytes, and their original
fresh/same-process fields describe the historical producer. The
separate archive-recovery.json records the later process, exact original archive,
restored file inventory, qualifier delta, and false fresh-build, native-rebuilt,
package-rebuilt and hardware-tested fields. The full original reproducibility
ZIP is copied byte-for-byte, never repacked. The release tag targets the original
compiled product commit, not the qualifier or publisher commit.

Factory .123 self-admission must admit all 43 internal ELFs in both ordinary and
sanitized host runs; retained SD admission must admit all 49 ELFs. The unsupported
.122-to-.123 preserving transition must remain rejected before ELF admission or
hardware/storage calls. A disposable authority-only control removes only Home's
new namespace-6 grant and admits the ELFs; it is never packaged. Both admission
modes bind the canonical digest of the delivered store, the locked baseline, and
the independently reconstructed control store. The offline
byte-range model does not establish preserving namespace eligibility.

The factory image erases internal saved settings and data when flashed at 0x0.
Hardware boot/update/rollback testing remains unperformed. Per-file serial
operations preserve unrelated files; this is separate from factory flash erasure.
The next paired firmware/full-payload release still waits for confirmed bootstrap
installation.

Validation: run tests/test_x4_bootstrap_publication.py and
 tests/test_x4_bootstrap_recovery_publication.py. Synthetic guard tests do not
replace exact-artifact admission, CI custody verification or hardware evidence.
