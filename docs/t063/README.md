# T063 delivered-source verification

The requested sleep and first-use RTC fixes are already present in Waveshare
0.1.32, T-Watch 1.1.29 and X4 0.1.114. No remaining defect was reproduced in
these paths, and no production sources or firmware were changed by this check.
There is no delivery hold. Physical-device confirmation remains outstanding.

- Waveshare Deep -7: vendor-panel fix `77087bee` closes transport and holds reset
  through scoped GPIO, with checked rollback. Production panel/RTC tests pass.
- X4 timer wake opening Home: hook `a7298c1f` prepares and commits SD storage
  before timer sleep. 143 scenarios across four configurations pass under UBSan.
- First RTC set: Utilities `80efb298` adds explicit verified clock-change
  notification paired with Settings 1.3.24 and Watch alarm service 0.4.9.
  The regression first reproduces the old error/Retry sequence, then verifies
  forward/backward edits, independent RTC verification, stale sleep tickets,
  due alarms, and error handling.
- First X4 alarm startup: the same Utilities checkpoint adds typed no-I/O BUSY
  retry in service 0.4.10. The qualified Home retains loading progress/defer.
  First boot, BUSY, catalog fault, Points and sleep regressions pass.

`tested-sources.json` records exact tested checkout identifiers. The Waveshare
source checkout is .31; the tested components are unchanged in delivered .32.
`delivered-components.json` compares actual delivered component hashes with the
corrected build. `x4-components.json` verifies .114's Home matches qualified
.107, alarm matches .106, and the sleep hook matches the qualified source hash.
The foreground clock repair is retained unchanged.

## Reproduce

Check out the named repositories at the exact commits in `tested-sources.json`.
Provide the five recorded Reader SDK headers under `DESK/sdk/driver`, with the
listed hashes. Run from this directory with Python 3 and a C compiler available:

```sh
python3 reproduce.py --x4 /path/to/X4 --wave /path/to/Waveshare \
  --watch /path/to/TWatch --utilities /path/to/Utilities \
  --settings /path/to/Watch-System --system /path/to/Clock-System \
  --runtime /path/to/Runtime --desk-sdk /path/to/DESK --output /tmp/t063-check
```

The script runs normal and UBSan checks; the X4 sleep matrix uses UBSan only.
Its compiler wrapper explicitly substitutes UBSan for the upstream runner's
hardcoded ASan/UBSan flags and corrects the final log label. The copied X4 shell
runner disables nounset for macOS Bash 3 empty arrays; test cases are unchanged.
The broad Wave driver runner initially stopped at an unrelated missing storage
SDK header; focused RTC and vendor-panel tests passed independently.

These are host models and byte/source provenance checks. They do not establish
physical wake success, RTC hardware reliability, or resolve a device report
that persists on these exact delivered images. No new firmware is warranted by
these results alone. See `result.json` and the committed logs for scope and limits.
