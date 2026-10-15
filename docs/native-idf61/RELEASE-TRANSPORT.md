# X4 0.1.122 native SDK release transport

Status: software-qualified transport, hardware validation pending. The pinned
manifest authorizes only the exact candidate bytes; it does not authorize a
rebuild, device flashing, main merge, or catalog operation.

The native product source checkpoint is `a9009a5d774ae7060b9f298fdcbc81be6c22cc17`.
The compiled Runtime source is `659d859acb122640ef4003bb8d7099501d4381be`.
Official [run 38797200408, attempt 1](https://github.com/michaelrolphone-cmyk/RiscRTE/actions/runs/38797200408/attempts/1)
passed all four lanes. X4 passed unchanged GPIO1, exact bootlog placement and IQ
proofs, retained 43 internal and 49 SD ELF admissions in normal and sanitized
campaigns, and all 496 preserving software fault cases. The 184-member original
X4 evidence ZIP is `7d2fc8059ff54fb08a65d66cbcd7ff53e709d8ccea3b34117a5286bb12c71e25`.
The Runtime public manifest SHA-256 is
`ddf5e3be350658b53bffa023fd3fbc9771c11fce25065f9bf6021ab5ca015d29`.

## Custody chain

1. Runtime's official successful controlled-build CI produces the original
   `native-idf6-x4-RUNTIME_SHA` artifact ZIP. Its stable archive roots are
   `candidate/`, `build/`, `metadata/` and `logs/`.
2. Runtime publication validates the successful official run, all required
   qualification records and artifact bytes. It publishes the exact original
   ZIP as `Runtime-0.4.0-X4-0.1.122-Native-IDF61-Evidence.zip` on the Runtime
   `firmware-v0.4.0` release, with a machine-readable source/run/hash manifest.
3. X4 publication is triggered only by an exact push of the fully pinned release
   manifest path on `work/native-idf-6.1`. It downloads the public Runtime
   manifest and ZIP by fixed repository/asset names and expected SHA-256s.
4. A read-only verifier checks safe archive paths, source/CI/hash agreement,
   source-lock equality, candidate asset hashes, native ELF/BIN/MAP input hashes,
   all X4-specific proofs, complete SD identity and hardware-pending flags.
5. Only the qualified factory, native image, exact complete SD package,
   original evidence ZIP, qualification/source records, instructions and checksums
   are staged. No source rebuild or repacking of firmware/SD payloads occurs.
6. A separate guarded job publishes a prerelease with those exact staged bytes,
   using only the repository's existing workflow token. Existing tags/releases
   must fail closed instead of being replaced or having assets clobbered.

The disabled `release/native-idf61/x4-0.1.122.example.json` remains a template.
The active `release/native-idf61/x4-0.1.122.json` pins the exact successful run,
source roles, public Runtime manifest and all qualified candidate hashes.
The path-triggered workflow fails closed if any required field or byte differs.

## User-facing limits

The SDK6 factory image erases internal saved data. The SD package is the exact
released 0.1.121 complete package, intended for merge/replace of matching paths
without formatting or deleting other SD content. It retains the existing
user-selected device-MSC SD transfer workflow.

No existing-bootloader preserving SDK-migration kit is emitted. Successful CI
cannot establish deployed-bootloader candidate boot, health confirmation,
rollback, physical GPIO/power behavior or hardware readiness. Those remain
hardware-pending and must be stated in release notes and the catalog record.

## Offline staging contract

The wrapper `scripts/native_idf61_release_transport.py` reuses the common outer
Runtime ZIP/manifest verifier, then applies all X4-specific admission, GPIO1,
external bootlog, final IQ, complete SD and ABI2 factory custody checks.
Use the example only as a template; missing hashes and `finalized=false` reject.
The Runtime public manifest is `Runtime-0.4.0-release-manifest.json` and binds
all four matrix artifacts, exact run/attempt/job/artifact IDs, source locks,
workflow hash, and every regular archive member digest.

```
python3 scripts/native_idf61_release_transport.py \
  --contract release/native-idf61/x4-0.1.122.json \
  --runtime-manifest runtime-release-manifest.json --evidence original.zip \
  --baseline-contract docs/native-idf61/released-baseline.json \
  --source-revision FULL_TRANSPORT_COMMIT --output NEW_OUTPUT
```

The transport source commit and compiled product commit are recorded separately.
This command never publishes, flashes, rebuilds, or creates new qualification.
Synthetic transport tests exercise exact-byte copying and rejection controls;
they are not candidate firmware qualification.

Local source-only transport checks: 20 common envelope tests and 10 X4 tests
pass. This includes exact original ZIP/SD copying and rejection of incomplete
49-ELF SD coverage, missing import negatives, wrong native proof identity,
changed hardware/preserving flags, and extra preserving-update assets. The
workflow YAML parses and targets only the approved native branch.

The publish job atomically creates the exact lightweight tag at the transport
commit and checks the returned ref/type/SHA before creating the prerelease with
`--verify-tag`. A tag that appears after the absence check therefore causes
publication to fail instead of being silently reused.
