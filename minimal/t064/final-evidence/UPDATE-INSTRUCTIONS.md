# X4 0.1.121 cumulative T064 test

Use the preserving-update kit only from exact 0.1.120. Follow its README: take a fresh complete readback, verify staged writes, and write selection LAST. Do not bypass planner refusal.

The separate `factory-erases-data-0x0.bin` is a full 16 MiB factory image and overwrites saved data.

Existing native firmware, partition layout and every non-Home application are byte-preserved. X4 keeps the existing cumulative .120 SD package, including GameBoy and OBDTest; no T064 SD replacement is needed.

Reports are saved in the internal AppData spool `/appdata/n0000003e/crash-spool.bin`. This path is not automatically exposed through USB. A qualified filesystem readback/extraction is required for internal retrieval; use the included `extract_crash_spool.py` on the recovered spool. SD export writes verified copies to `/CrashReports/` and retries when media returns, including after USB export ends.

The queue holds eight reports. A full queue preserves existing entries and leaves new native evidence unacknowledged. The report is acknowledged only after every page was presented and its exact text was durably saved. This does not promise unlimited history or survival of RTC evidence across loss of power before durable capture.

Normal and ASan/UBSan spool, archive, session, renderer and actual paginated Home tests passed. RGB pixel/native-height regressions passed across 362 golden frames. Full source-bound Runtime admission passed for 43 X4, 62 Waveshare and 59 T-Watch ELFs, with exact-baseline preserving-update fault tests. X4 target CI reproduced the deployed baseline and two identical candidate builds. No hardware qualification is claimed.

Factory SHA-256: `48145adc023a334885207100ce29596edef3f02c07a6d830ca53e3ab1fbf5993`
