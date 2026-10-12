# X4 .93 minute-wake correction

Scope: the X4-owned timer-only desk-clock sleep hook, diagnostics at safe
boundaries, and tests. Shared System application/native Runtime sources are
unchanged in the distributable. Home package becomes 0.4.12; Files remains 1.5.30.

## Cause and reproduction

Automatic device sessions 47 and 48 report reset 8/wake 4, valid retained timer
classification, mounted SDMMC transport, timer-ready and minute-frame completion,
then foreground promotion 290–336 ms later. These are timer boots, not manual resets.

Runtime 3b90cd11cf0ff4e8116bb54d2d9eb9c7c67a148b NativeHardware deepReady requires
NativeSdmmc::closed(). Provider loading mounts SD even on the sparse timer route.
The old timer hook prepared only the panel; native sleep therefore refused the
open SD transport and the ordinary clean-refusal path promoted Home. The real
Home controller/adapter/product hook with a deterministic SD-open native gate
reproduces this failure on the unmodified .92 hook. This model is not physical
provider execution; hardware logs locate the same path but do not contain the
old native refusal's exact return code.

## Change

Timer sleep acquires the already-authorized storage.volume instance 9 and invokes
its checked prepare/commit after panel preparation. Rollback resumes storage
first; unavailable media is recoverable, while retained/refused/unknown custody
prevents further I/O or release. Touch/navigation/radios remain unstarted on
healthy timer boots. Minute/alarm deadlines are still charged for preparation.
The same retained 408-byte schema, clock orientation and dark timer behavior apply.

Small wake/refusal diagnostics use the existing buffered boot logger only after
safe grant release. No additional SD writes or serial dependency are introduced
under prepared resources. Timer log persistence is tested across repeated boots.

## Validation

- Original hook reproduces minute-render followed by Home on mounted-SD refusal.
- Fixed full resident/installed-catalog profile: 64 normal/ASan+UBSan cases cover
  orientations, asynchronous frame completion, repeated retained 408-byte wakes,
  alarm/catalog refresh and terminal fences.
- Strict client: 143 scenarios × 4 configurations pass normal and UBSan, including
  held buttons, due alarms, absent SD, fourth-grant acquire/release, malformed
  descriptors, failed preparation/commit and every resume custody outcome.
- Actual SD provider host and buffered-log suites pass normal/ASan+UBSan.
- Xtensa Home target structural admission and imports/exports pass.
- Composer independently decodes actual final SPIFFS and bank-state bytes, allows
  only default.elf/default.json/cohort.json changes and preserves native, all
  other internal packages, all 81 SD files and 46 selected SD images.

Host proofs do not establish repeated physical minute sleep/wake success. Device
qualification remains pending. The full initial BIN must be flashed at 0x0 and
erases internal settings, saved networks and app data. Existing complete .90 SD
contents remain required; no SD overlay is needed for this change.
