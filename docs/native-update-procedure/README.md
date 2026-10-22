# X4 update qualification procedure: blocked preparation draft

**NOT RUNNABLE DEVICE INSTRUCTIONS. NO HARDWARE ACCEPTANCE.**
This additive package binds the existing X4 PR #48 preparation to the unchanged
shared preservation matrix. It does not publish firmware, finalize a manifest,
operate a device, merge a PR, change production pins or grant installation authority.
The producer and frozen 46-case matrix remain their respective owners' work.

## Bound source, not a release

- Product: [PR #48](https://github.com/michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO/pull/48),
  `ee832b0c16c26f76dd15a27e318d61c478d38d3c`.
- Existing candidate build: [CI 39363726868](https://github.com/michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO/actions/runs/39363726868).
  This is prior build/software evidence, not this procedure's test result.
- Shared matrix: [PR #87](https://github.com/michaelrolphone-cmyk/RiscRTE/pull/87),
  `b3a846b5252c00a849c560ced936b1ce4baab260`,
  `docs/catalog-preservation/1.0.0`. Preserve every case and named variant.
- `inputs.json` locks exact source-file hashes and actual CI artifact members.
  The artifact expires 2026-11-19 at 03:37:21 UTC. Expiration is a reproducibility
  stop gate, not permission to create a release or substitute other bytes.

The actual prepared SD ZIP is 11,023,620 bytes, SHA-256
`d4c5598b2d7f7c6022f53bcd0bb5479b90f3dd1fb53a9a8936f55d1f3a09928d`.
The factory is 16,777,216 bytes, SHA-256
`f4f7deadb7e6f2e278c0e0af90c3633c48e4f531317f9d513e905fb26f4cc01b`.
The SD contains 78 files. ZIP size is not the sum of uncompressed payload lengths.
The exact denominator, paths and complete byte hashes are in `inputs.json`.
These hashes establish preparation byte identity only.

## Stop gates before a runnable handoff can exist

1. Explicit installed .123 bootstrap evidence, exact device/firmware identity,
   actual board revision, observation timestamp and supported recovery route.
   The released .123 baseline is not proof that it is installed on any device.
2. Actual published .124 release ID/tag/immutable source, exact asset URLs and
   readback hashes; fresh authenticated Catalog release and payload-plan revisions.
   Proposed release URLs embedded in fixture manifests are not verified links.
3. Independently reviewed nonfixture board/trust context and consumer mapping,
   current HELLO/namespace discovery before and after the firmware transition,
   provider availability/capability/path/capacity bounds, and safe custody.
4. Nonfixture manifest/container and ordinary frozen-schema semantic validation;
   the source producer's `finalize` prerequisites still apply. Do not copy the
   fixture release ID 1, `fixture-unspecified`, or self-asserted trusted context.
5. Approved test destinations, backups, independent observations and supported
   recovery details. Protect real user data. Public source/result examples must
   not contain private settings, identifiers or actual user-file content.
6. A separate authorized hardware execution and review. This package cannot clear
   any gate, even when all preparation checks pass.

## Candidate-bound sequence and separate observations

The only prepared order is **firmware → payload → verify**. The source-declared
method is a full factory image at offset zero. It erases internal saved settings
and data; external-volume survival is unknown, not preserved. These are declared
semantics to measure, not claimed physical observations. Do not infer a preserving
installer, OTA, rollback or power-loss durability.

Use distinct eventual records, not executable commands here:

- F0/F1: all selected targets, independent sentinels and native settings immediately
  before/after the exact authorized firmware method. Record declared and observed
  effects separately, including unknowns; do not blame flashing changes on serial.
- Re-identify running firmware and re-admit mapping after flashing. Take fresh S0
  before any serial interval, including every negative/fault case. Reestablish a
  non-default persistent settings sentinel after the erasing flash.
- S0/S1: selected-path existence/type/length/full hash plus unrelated sibling,
  sibling-directory/known-tree inventory, user-file and native-settings sentinels
  observed independently immediately before/after each serial interval.
- S2: supported restart kind/timing, complete payload readback and all sentinels
  through their owners. Do not use uploader cache/source echo/progress as evidence.
  Record unrelated admitted-volume sentinels when available. RTEF1 has no LIST.

The candidate expects logical volume `application-content`, wire namespace **12**,
provider `x4pro-sd`, provider instance **9**. Namespace 12 is not instance 12 or
instance 9. This is source/fixture expectation, not live admission. Namespace 1 is
immutable active boot storage; namespace 2 is private scratch, not a destination.
Never route by SD/SPIFFS labels, mount roots, fallback or provider-instance numbers.
Record actual provider bounds; do not promote fixture capacity values to hardware.

## Three full-payload scenarios and recovery

Each eventual scenario needs its own shared result record and fixed 78-file
inventory. Do not erase/reformat a card to make these preconditions true.

1. Clean targets: independently establish every required path absent; explicitly
   select create for all 78. Other user paths remain untouched.
2. Existing .123 contents: inspect every exact destination and explicitly approve
   the operation plan. The CI fixture illustrates 77 replace plus one create only
   when those preconditions are independently true. It is not an auto-selector.
3. Repeat/idempotent content: with all 78 present, explicitly selected replace must
   yield identical full bytes and unchanged unrelated sentinels. A repeat create
   must fail EXISTS without silently switching modes. Idempotent end-state does
   not mean atomic replacement: PUT replacement truncates immediately.

For each required file, include exact volume/path, chosen operation, initial state,
expected/actual full length/SHA-256, CRC and COMMIT/CLOSE acknowledgments, attempted
and acknowledged offsets, all-file denominator, timestamps and evidence links.
Canonical parent-first directory checks create only on authoritative NOT_FOUND;
no recursive folder replacement, unsupported rename/delete/format or activation.
A missing/failed final file leaves the whole update incomplete despite earlier
success. Record effects rather than resetting totals to hide them.

Interrupted transfer, disconnect, timeout, lost PUT/COMMIT ACK, malformed reply,
sequence/offset mismatch or retained custody must retain the original failed or
unverified attempt. No automatic retry/reconnect/reset/cleanup after uncertainty.
Definite failure with known custody follows the pinned client's bounded best-effort
ABORT semantics only. ABORT does not delete partial creates or restore replacements.
After separately authorized supported recovery and safe custody, re-identify/re-admit
using a fresh session, inspect the selected path and append a new linked recovery
receipt. Retained custody requires real restart; time or host close is not proof.
Lost COMMIT ACK may reconcile by separate complete readback, never invented ACKs.

## Every case and every result stays explicit

`draft.json` is generated from the pinned shared `result-template.json`. It preserves
all 46 cases and 85 named variants unexecuted, adds per-case X4 binding notes and
78 unverified file-result rows. Shared stimuli/expected outcomes remain in the
pinned matrix, not a divergent local copy. Scenario templates, sentinel requirements,
bootstrap and final identity fields remain visibly unbound.

Protocol faults unsafe/impossible on the product require exact-source software
injection with reproducible hooks/transcripts and explicit substitute coverage.
Conditional flat/nested paths require actual capability evidence, not automatic
exclusion. Existing producer host tests used a POSIX namespace-1 fixture and do not
establish physical namespace-12 SD behavior. Their historical results are not new
matrix coverage. Keep software/hardware/mixed evidence scopes distinct.

For physical acceptance, final all-file readback, restart persistence and actual
consumer usability must be physical, after the last firmware step. Cover all
resources via actual consumers or a per-file consumer-load/inventory trace. Do not
activate radio/network applications as a side effect of this preparation. Any future
consumer exercise needs its own authorized, safe scope. Final read-only admission
may permit verification, never upload. Reject transfer-first with unknown effects.

Pass criteria: 100% required files match full length/SHA-256 and are consumer-usable
after restart; zero unrelated serial-interval changes; every applicable case/variant
has evidence of its expected behavior; actual flash effects are separately reported;
no failed/unverified operation is presented as success. Shared `review_result.py`
checks record consistency only. It is neither product execution nor acceptance.

## Preparation-only checks

`bind.py` reads pinned sources and the exact downloaded Actions ZIP, checks full
artifact/member/payload byte identity, and produces `draft.json` deterministically.
It performs no networking or device I/O and has no finalize/execute mode. Run its
negative controls and then `--check` against a freshly verified remote commit.
The workflow supplies the exact sources and artifact; no firmware rebuild occurs.

With the pinned Runtime checkout and candidate Actions ZIP available locally:

```sh
PYTHONDONTWRITEBYTECODE=1 python docs/native-update-procedure/bind.py \
  --matrix /path/to/pinned-runtime --artifact /path/to/candidate.zip --check
PYTHONDONTWRITEBYTECODE=1 python docs/native-update-procedure/test_binding.py \
  --matrix /path/to/pinned-runtime --artifact /path/to/candidate.zip
```

These checks authenticate neither a device nor trust-context authority. They compare
exact pinned bytes and reject altered source, archive, inventory, order, routing and
false preservation claims. The generated unexecuted draft must fail the existing
shared report checker. `draft.json` is not a new acceptance validator or an executable
operation plan; actual operation choices and all observed evidence stay null.
