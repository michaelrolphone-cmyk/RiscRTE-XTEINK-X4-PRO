# X4 .78 source successor: Wi-Fi 1.1.26

Use System source **600e56bc08962c0473735b2fd5d5d80aa62b77a8**, branch
`fix/wifi-profile-persistence-078`. It includes the published **1.1.25** scan
lifecycle fix and adds successful-connection persistence for the selected X4
resident profile. The prior .78 Wi-Fi required a separate Save action; connection
success never wrote a profile. Connected polling also hid save results/errors,
and a failed Forget discarded the selected draft. All three behaviors are fixed.

Successful association now queues one save using a copy of the submitted
credentials. Different SSIDs retain independent profiles. Existing SSIDs update
in place; edits and explicit Save remain supported. Save errors remain visible;
failed Forget retains its selection for retry. Storage-service leases cover
save transactions, so worker contention before a save defers without partial
writes. Pending saves participate in cooperative close; Back can cancel.
The shared masked keyboard is retained. No credentials are logged.

The delivered `boot.json` authorizes namespace **6** through the existing
`storage.key-value@1` API, which native NVS maps to **rte00000006**. No grant/key
mismatch was found. The existing codec/index and native commit/readback path
remain unchanged. This source does **not** migrate settings to SD or alter the
storage API/backend; it is compatible with separate work that later replaces
the backend while preserving that contract.

## Exact build and integration

Use the same command and pinned compiler/SDK/Utilities inputs in
[the scan repair recipe](WIFI-RESIDENT-078-FIX.md), selecting the System commit
above and a new output directory. Its builder enables
`PORTABLE_WIFI_REMEMBER_CONNECTED` only for the resident X4 app and emits
**1.1.26**. The checked-in `docs/evidence/wifi-persistence-078/target-build.json`
contains the complete command, source/SDK hashes and clean source receipt.

Target ELF SHA-256:
`e5df0a788f2f4d1c2d7faff3109110da54a476c416f4b4894248f92ccb1d694b`.
Size: **234264 bytes**, unstripped. Do not substitute earlier development outputs.

Replace only internal `wifi_settings.elf` and its matching `wifi_settings.json`
in a new coordinated, versioned assembly. Refresh cohort hashes and run the
existing full-image admission/readback workflow. Wi-Fi remains internal; an SD
copy alone does not select this replacement. Capability requirements are identical
to .78; only the manifest version changes. Native Runtime remains **0.2.5** at
`7071f0c25e223f24670bed409a5f8b6f291c8042`, Wi-Fi provider **0.2.1** at
`a304597bf26491483bb0a567569f0ca0267cdf9c`.

Preserve Reader **0.1.8**, Daily Paper **0.1.0**, panel **0.1.12**, Scene **0.3.6**,
Home **0.4.8**, Springboard **1.7.31**, SD app split and every other .78 artifact.
Do not rebuild other components from this intentionally narrow historical branch.
The decoupled input/presentation pipeline and `--raster-snapshot` stay selected.
This checkpoint does not incorporate the separate USB or SD settings tasks.

## Evidence and limits

- Baseline successful-connection persistence probe fails; fixed probe passes.
- Normal/UBSan tests execute the actual controller, profile codec and native NVS
  adapter against a disk-backed synthetic NVS SDK. Separate processes verify
  cold-start loading with no app globals or grants surviving between processes.
- Two different networks coexist; tests cover reentry, saved selection, masked
  password edit, failed/successful delete, empty-slot reuse, failed association
  with no writes, BUSY with no writes, save failure/retry, pending close, copied
  submitted credentials despite later draft edits, and open networks.
- Existing 56 controller workflows per mode, 50-profile transactional faults,
  and normal/UBSan resident-scan/native-worker regressions pass.
- Clean Xtensa compilation, ELF structural validation and import/export checks
  pass. The manifest matches .78 except its version.

Radio, outer grants, peripherals and the NVS SDK boundary are synthetic; the
namespace grant was separately audited from the delivered boot file. Cold-process
tests do not establish hardware flash durability or physical reboot behavior.
No full image was assembled, hardware operated, device flashed, master merged,
or release published. Full-image integration and a hardware persistence retest
remain necessary.
