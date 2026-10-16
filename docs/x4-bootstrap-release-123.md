# Guarded X4 0.1.123 publication

The transport contract gates staging separately from publication. Unresolved
pins keep both gates closed. A finalized contract with `publication_enabled: false`
authorizes read-only verification and staging only. Publishing transport source
does not authorize a release.

## Two independent source identities

The same-process producer path requires an exact successful
`native-provision-123.yml` push/manual run or same-repository PR45 run, with its
immutable product commit/tree, all eight dependency source locks, workflow hash,
run/attempt/job IDs and three artifact IDs/digests. The explicitly selected
[archived-byte recovery path](../release/x4-bootstrap-123/RECOVERY.md) preserves
the original failed producer identity and separately pins a successful qualifier
source/run; it cannot relabel the original failure or rebuild its packages. The publisher
is this transport checkout on `work/x4-bootstrap-release-123`. The reserved tag
`test-native-provision-0.1.123` points to the qualified producer commit, never the
publisher commit. Both identities are recorded in `release.json`.
The run/job/artifact head SHAs bind historical source; GitHub
`pull_requests[].head.sha` is mutable after a PR advances. PR number/ref and
head/base repository IDs still must match. Artifact creation must fall within
the exact successful job attempt, rejecting artifacts left from an older retry.

No native build is performed. No candidate, SD archive, feed, payload or original
CI archive is repacked or rewritten. Public feed assets are copied from
`feed/assets/` to the release root, exactly where the already-compiled and frozen
URLs point. Candidate `store/` and all individual-file semantics remain in the
original candidate evidence ZIP. The complete SD ZIP retains its .121 filename,
size and hash; merge/replace matching paths without deleting unrelated files.

## Finalize only after qualification

1. Independently inspect the successful qualification and exact compiled producer.
   Recovery requires both original failed and later successful run attempts. Record
   `source_revision`, `source_tree` and the original full `source-lock.json` sources.
2. Pin the exact run/attempt/workflow/job and source workflow SHA-256. Pin all
   three transported artifact IDs, exact names, archive sizes and SHA-256 digests.
   Recovery additionally pins the original bounded qualification and later
   admission-input artifacts, custody receipt and original archive contract.
   Pin qualification JSON, candidate SHA256SUMS, source baseline and source-input
   digests, all six native/SD asset records, and the entire qualification feed
   inventory. Artifact hashes refer to the original downloaded ZIP bytes.
3. Set `finalized: true` with `publication_enabled: false`. Push to the dedicated
   publisher branch to run guards and bounded transport without release writes.
   Stage verifies live official API provenance. Qualification and candidate
   archives each have a 512 MiB transport bound and bounded ZIP inspection. The
   complete reproducibility ZIP has a separate compressed-byte bound strictly
   below 2 GiB. It is streamed, SHA-256 checked and retained byte-for-byte as
   `reproducibility-evidence.zip`, without expansion or repacking. This preserves
   the full source/SDK/build evidence beyond the original Actions retention.
   A separate bounded staging-review artifact copies only the unchanged
   `release.json`, `SHA256SUMS`, `transport-contract.json` and `RELEASE-NOTES.txt`
   for independent inspection. Publication consumes the complete main artifact.
4. Review the staged exact bytes and warning. Publication is a separate approved
   change of `publication_enabled` to true. Do not modify qualification or feed
   files to make a failing check pass. A mismatched shape must be investigated.
5. Publication rechecks provenance, refuses any existing exact tag or release,
   atomically creates the lightweight tag at the qualified producer, then creates
   a draft prerelease. It uploads without `--clobber`, verifies the entire asset
   inventory and redownloads every byte before making the draft public. It then
   redownloads and verifies every public release asset again without credentials,
   directly from its frozen HTTPS URL (HTTPS-only redirects, bounded bytes/time). Large evidence readback is streamed; it is never loaded
   as a single in-memory value or extracted.
   The public check cannot be satisfied by authenticated API access. API errors fail
   closed. No cleanup, replacement, deletion or automatic resume is attempted.

If tag creation succeeds but a later operation fails, the tag and any draft are
left for explicit investigation. A collision (even identical existing bytes)
never silently becomes permission to mutate an existing release. A final public
readback failure is a failed publication verification, not a successful release.

## Installation boundary

The factory image must be exactly 16 MiB and is named
`factory-candidate-erases-data-0x0.bin`. Flashing it erases internal saved settings
and data. The separate firmware, bootloader, partition and store files do not
constitute an independent flashing procedure. No data-preserving migration or
OTA kit is delivered. Hardware boot/health/rollback remain pending. A subsequent
paired firmware/full-payload release waits for confirmed user installation of
this bootstrap. RTEF1 is ordinary file transfer, not firmware flashing or package
installation.

## Host verification

Run `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_x4_bootstrap_publication.py`.
The tests use synthetic bytes and a fake API, never firmware builds, GitHub
mutations or hardware. Existing .122 recipes and provenance are untouched.
