# X4 .94 startup and file-loading qualification

Working checkpoint. No device speed or hardware sleep/wake qualification is
claimed. The baseline is the exact delivered .93 image, SHA-256
`13262f6878e99252ec4eb861e3dfe18ead8ac37937ea26636752bd3ccb06f7f4`.

The native candidate carries only the qualified regular-file ELF `fstat` size
query and bounded metadata-read cooperation from Watch, applied to X4 Runtime
3b90 plus its own version increment. It preserves the X4 early rail hook,
capacity settings, native API tables, whole-graph admission, original fallback
seek path and storage/error/retention handling. Watch power/input profiles are
not imported. A matching clean native source, firmware and ELF are required.

The selected Home .4.13 profile defers nonessential foreground services until
presentation and input are available. Alarm and Points dependencies, touch,
navigation, preferences, orientation and interactive frontlight remain on their
correct paths. Timer-only execution retains its original closure, and the .93
product-owned SD prepare/commit/rollback sleep transaction is byte-identical.
The new selection is opt-in; other shared app profiles retain their startup.

The .94 composer independently decodes final SPIFFS bytes and bank state. Only
the native application partition, Home ELF/manifest, cohort identity, bootfs and
bank digests may change. Boot authority, all other internal packages including
Files 1.5.30, the 81-file SD tree and its 46 selected ELFs stay byte-identical.
Bootloader, partitions, initial app-data and unrelated flash ranges are checked.
The composer requires exact source commits, qualification hashes and native
linkage proofs before creating a deliverable. Its synthetic roundtrip probes
never create an installable output.

The delivered artifact, if qualified, is a raw 16 MiB full initial image flashed
at offset 0x0. It erases internal settings, saved Wi-Fi networks and app data.
Existing complete .90 SD contents remain required. An unchanged SD tree is not
redelivered. Hardware acceptance must separately check repeated minute wakes,
button wake/frontlight, due alarms, Points, Files, radio settings and real
boot/wake latency under matching device settings.
