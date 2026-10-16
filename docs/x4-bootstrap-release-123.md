# Guarded X4 0.1.123 publication

The committed contract is disabled and deliberately unresolved. It cannot stage
or publish. Failed native run 38965239367 is not eligible. Publishing this source
preparation does not authorize a release.

## Two independent source identities

The producer is the exact successful `native-provision-123.yml` push/manual run or same-repository PR45
run, with its immutable product commit/tree, all eight dependency source locks,
workflow hash, run/attempt/job IDs and three artifact IDs/digests. The publisher
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

1. Independently inspect the successful producer run and qualification. Record
   `source_revision`, `source_tree` and the exact full `source-lock.json` sources.
2. Pin the exact run/attempt/workflow/job and source workflow SHA-256. Pin all
   three official artifact IDs, exact names, archive sizes and SHA-256 digests.
   Pin qualification JSON, candidate SHA256SUMS, source baseline and source-input
   digests, all six native/SD asset records, and the entire qualification feed
   inventory. Artifact hashes refer to the original downloaded ZIP bytes.
3. Set `finalized: true` with `publication_enabled: false`. Push to the dedicated
   publisher branch to run guards and bounded transport without release writes.
   Stage verifies live official API provenance and downloads only qualification
   and candidate artifacts (each at most 512 MiB). The reproducibility archive's
   ID/size/API digest is pinned and verified, but that larger archive is not
   downloaded or republished by this bounded transport.
4. Review the staged exact bytes and warning. Publication is a separate approved
   change of `publication_enabled` to true. Do not modify qualification or feed
   files to make a failing check pass. A mismatched shape must be investigated.
5. Publication rechecks provenance, refuses any existing exact tag or release,
   atomically creates the lightweight tag at the qualified producer, then creates
   a draft prerelease. It uploads without `--clobber`, verifies the entire asset
   inventory and redownloads every byte before making the draft public. It then
   redownloads and verifies every public release asset again without credentials,
   directly from its frozen HTTPS URL (HTTPS-only redirects, bounded bytes/time).
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
