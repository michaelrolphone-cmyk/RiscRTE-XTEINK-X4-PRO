X4 0.1.112 ordered input parity test checkpoint

System f74db7d ports the existing mature X4 ordered reducer to the older Watch adapter. Deployed .111 System 1db9915 already calls portable_touch_collect in input_service and dispatches exactly one edge per controller pass in input_dispatch. PortableTouch.h is identical to current X4 System 8a5ef23; the only difference from f74db7d is release_position_valid being gated by PORTABLE_TOUCH_SCROLL. This Watch-specific metadata unguarding does not require replacement of X4 binaries.

This test composition increments only cohort version and source identity. All 43 internal ELFs, all app manifests, panel 0.1.12, native Runtime a91edf3, Home, RTC reconciliation, OBDTest registration and current SDR fixes remain byte-identical to .111. The cumulative changed-SD overlay is unchanged from .111 and contains existing RF/Points/Scanner packages; there are no additional SD input-fix changes. Never describe this as newly fixing X4 ordered input.

Shared source regression evidence is attached, including 75 X4 scene/cadence cases. No serial, flashing or hardware qualification. Factory firmware erases existing device data.
