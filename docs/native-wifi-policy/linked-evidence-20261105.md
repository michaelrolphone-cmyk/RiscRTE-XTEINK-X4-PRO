# X4 Wi-Fi native link evidence, 2026-11-05

This receipt note records a source-bound CI result, not installed firmware or product admission.

- Product: 762e5a458d56e9582b839c2fbe30109911f36f92, tree 5aed2c56f731e69974e45a993301307de6649ac9.
- Runtime: fb6d0323b7ab6fa57af8fd5551ce45fdf52c743d, tree 421df33e61d75e209c52ddfe26bdc491d268472f.
- SDK: fff9895c82d744c7237be8847347bdd1b07c6643.
- Official IDF image digest: sha256:81893c71bb5e570088901f21def8684c25cd2a9020281bd01b843a7655edb18c.
- [Successful native run](https://github.com/michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO/actions/runs/42014116122), job 127200188459.
- Artifact 13409920368, 150315374 bytes. ZIP SHA256 cdc8035b8c32b9fcf26ca3ce4957e4b1e7ca327520fd1799cd0dec8ca2f50b3e.

Both the successor profiles/native-wifi.cmake and unchanged predecessor
profiles/native-provision-123.cmake pass the existing IQ post-link guard,
linked-native boundary test and exact compiler/link/source closure checks.
The focused production-selected host admission controls also pass.
This compares both profiles against the same new Runtime; it is not a reconstruction
of a historical released binary.

## Measured bounds

Both profiles have .dram0.bss size 24344 bytes beginning at 0x3fcaa0d8 and
ending at 0x3fcafff0. The IQ bank begins at 0x3fcb0000: only 16 bytes remain.
No IQ bank address, section placement, feature or limit was changed.
NativeSettingsLifecycle::state is 1088 bytes for the seven-binding/six-identity
successor and 1080 bytes for the six-binding predecessor.
The previous failed successor had a 1200-byte State and 24456-byte BSS.
Copied identity separation removes that measured overlap without dropping bindings.

Relative to the same-Runtime predecessor, successor firmware adds 2736 bytes,
flash text adds 2672 bytes, and flash rodata adds 64 bytes. BSS, data, IRAM
and external BSS sizes are unchanged. Firmware sizes are 1822112 and 1819376 bytes.

- Successor firmware SHA256 a10e372940ab5b8af2f610abf06e40bc60b5129483e674af60ad8f931747daaa.
- Successor ELF SHA256 529b4e677968d57cf1ca0bbf312a3043354338f7f1a1901a24afa14373783062.
- Successor map SHA256 3b8cff2983564ec3c542344168af876626662223aea124e75e1e24546755ced9.
- receipt-successor/build-receipt.json SHA256 f73d99d6776b04fa7b2a6cea02f78a7b4eeccdfaa77c0e20afadbc3a4eeca3eb.
- receipt-previous/build-receipt.json SHA256 2fb82237f36b853708c7e29e002389d11f5959845f99ef88e435c2dcf3091208.

The artifact retains both builds, ELF/map, generated profile identity, SDK configuration,
compile commands, stack-usage files, dependency receipts and logs.

## Remaining gates

Static link success does not establish heap peak, allocator overhead, fragmentation,
cumulative stack high-water, shared AppData safe replacement space, reboot preservation,
full foreground/Home behavior, or final app/provider/native cohort admission.
No deployment or release was performed. Runtime source receipts must match the exact
native firmware and app/provider qualification source set.

Any combined Runtime successor, including LocalOnly policy work, requires a fresh
native build and IQ check for both profiles. This receipt must not be relabeled or
reused for a different Runtime pin. The 16-byte margin is not product heap headroom.

## Fresh Runtime 0.4.22 qualification

A separate build, not a relabeled receipt, qualifies product
75becdb44a914e749cd64385c3897832c78c3476 with Runtime
286d7da65d5151dfa3840989ce8917dfa23e6856 (version 0.4.22).
[Run42018261648](https://github.com/michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO/actions/runs/42018261648),
job127214148223, passes both native profiles, IQ and source/dependency closure.
State sizes1088/1080 bytes and both BSS endpoints0x3fcafff0 remain unchanged,
leaving the same16-byte margin. All remaining admission limits above still apply.

Artifact13411775209 is150312107 bytes; ZIP SHA256
fb2aa6f574912f2ac1d91de3de9d691fe7c9fdfbd61894fa2d879e0ecf7181b0.
Successor firmware SHA256 bf5882135270f9a4adb3b76ee2ab1da1a000923403c38cf2d65025ee3c61f34b;
ELF SHA256833244c48217fffc1ea2fd1bc94a35d00ade0493248164741d3dc977c92a6c9b.
The successor map SHA256 remains3b8cff2983564ec3c542344168af876626662223aea124e75e1e24546755ced9.
Successor build-receipt SHA256 c425529041f563a0936f6206ff417c345316e066fd685eed32f4f548fad2c89a;
predecessor377d67cd05fa61cfda30fd5153583350a624e87b8adbf4d2e70ecb627dacb6d5.
The separate Runtimeaa60686 host negative tests are qualification-only changes;
their success does not replace this exact286d7da native receipt or establish a
different compiled firmware identity.

## Independent backend refusal evidence

Runtime aa60686e0043d3ae72b774915f704b87f55794ca adds only host qualification
changes after286d7da. [Run42019706349](https://github.com/michaelrolphone-cmyk/RiscRTE/actions/runs/42019706349)
passes both normal(job127219098351) and ASan/UBSan(job127219097827) campaigns.
The host fixture SDK uses X4c8004c5c8362b142ebb35a0e1c5d266532a11581 and
Reader7e91fa4a6819ba45659d9f8975c3e2646122137a, with strict overlapping header equality.
Those are fixture inputs, not the selected native firmware identity.

Actual pinned LittleFS reports495616/524288 bytes used,28672 free after96
fixture filler files. Both namespaces1 and6 return NoSpace without changing
the fixture flash image, NVS records or Core revision. Recreated Core/store views
reload the selected values. Removing only fixture-owned filler permits retries,
while ordinary peer bytes and both original legacy NVS namespaces remain unchanged.

First-payload-allocation refusal returns NoMemory for each namespace, with one
PSRAM allocation request and no fallback. Flash/NVS/revision remain unchanged;
reload and subsequent retry succeed. Existing adapter tests pass range/alignment,
overflow, wipe-before-free and2000 concurrent cycles.

Normal artifact13410992438:1377019 bytes, ZIP SHA256
076231c6435e13ed80276cabf99033a4c1a788fd0d1293b489cffcaf1a1a5b8e.
Sanitized artifact13410952625:3494606 bytes, ZIP SHA256
1895c618a15534d0632587c7b1af0664ace023ac34a2a5a2159ae8cc8250bf34.

Selected requested-payload peaks are331593 bytes(atomic),396728(sync),
and331476(first export), identically reported by both modes.
They exclude vendor/STL allocations, allocator headers and fragmentation; they
are not available heap or a product budget. The tests model worker/NVS/Assembly
boundaries, exercise object reload rather than physical reboot, and prove operation-time
refusal rather than a durable shared-AppData reservation. Full cohort, cumulative
stack, coexistence heap and cross-writer/reboot replacement guarantees remain open.
