# X4 reversible Light sleep: exact frontlight qualification

This is test-only qualification of the unchanged production
`minimal/apps/portable_idle_sleep.c`, linked to the actual Utilities alarm
service via its production test fixture. Hardware and Runtime calls are fixtures;
the saved brightness input is controlled by the test. This does not qualify a
physical panel, preference persistence, the full resident UI, or deep/GPIO wake.

## Assertions

- All 59 existing idle/alarm scenarios still run.
- Saved levels 0, 40 and 73 each run through normal wake, repeated wake, no-UI
  wake, native refusal/unsupported, prepared cancellation, panel/touch refusal,
  SD prepare/commit refusal, and restoration-setter failure.
- Clean returns assert the final exact level, darkness consistent with that
  level, and an ordered pair of setter calls `[0, saved]` per attempted sleep.
  Repeated wake checks both cycles, so a later restoration cannot hide a failure
  in the first. Unprepared early returns make no brightness calls.
- Setter failure, including a failed request to restore 0, returns retained with
  all six grants retained, the overlay still owned, and no subsequent hardware
  or alarm-provider I/O. The fixture does not assume a failed setter changed
  the physical level.
- Two temporary source mutations remove restoration or replace the saved value
  with 40. Each must abort at the exact level/count assertion for normal,
  repeated, refused and cancelled flows at levels 0 and 73. A compile failure,
  unrelated crash, or sanitizer diagnostic is not accepted as mutation detection.

The total is 92 normal + 92 ASan/UBSan positive scenarios, plus 16 normal +
16 ASan/UBSan rejected negative controls. Mutations exist only in the test
output directory; the tracked production helper stays unchanged.

## Reproduce

Use the pinned dependencies in `.github/workflows/idle-frontlight-qualification.yml`.
Compose Reader's driver SDK with this repository's `minimal/interfaces` overlay,
then run:

```sh
python minimal/test/run_idle_alarm_sleep_test.py \
  --system /path/to/system --runtime /path/to/runtime \
  --utilities /path/to/utilities --driver-sdk /path/to/composed-driver-sdk \
  --output /tmp/x4-idle-frontlight
```

Alternatively, `--candidate /path/to/composed-home` uses an existing
`idle-sdk/include`, preserving the runner's original input contract. Source-only
staging uses System's actual alarm/idle SDK composers and selected canonical
Runtime interfaces. It deliberately preserves the application-owned battery ABI
instead of overlaying every raw Reader driver header. It builds host tests only.

`receipt.json` records the production helper hash, exact compiler dependencies
and their hashes, compiler commands, positive outcomes and the negative-control
assertion diagnostics. CI runs on the PR and on changed `main`.
