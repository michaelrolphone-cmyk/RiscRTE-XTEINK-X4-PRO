# X4 0.1.95: boot-order store placement

The .94 device log reports manifest preparation taking 5.364135 seconds,
first display submission at 8.905 seconds after native boot, and completion at
11.068 seconds. The log starts partway through boot and has no source banner;
its after-Home radio marker confirms the new deferral path, not a cryptographic
image identity. These measurements describe .94 only.

SPIFFS searches names forward from its previous lookup cursor. Alphabetical
packing separates the boot manifests with large ELF files and makes successive
manifest opens repeatedly scan most of the store. This recipe changes physical
file order, not Runtime, manifests, grants, provider activation or ELF contents.

The production Runtime.prepare host trace supplies the 61 metadata reads:
boot, board, driver manifests, application manifests, with cohort.json at the
first retained-wake grant. They are packed in that order, followed by the default
ELF, internal bootstrap providers, the measured foreground provider closure and
remaining ASCII paths. The pinned IDF producer and independent decoder are reused
unchanged. No filesystem index, SDK patch, or validation bypass is introduced.

## Exact byte custody

Baseline: published X4 .94 source 16ce5f68002c77d79e10feb7e794437d2b16b8b5,
full BIN SHA256 f4a00dfb23d14bc41ce55bedb4b5e36ee15ea32d1c92817119ba0a21431ec634.
The recipe SHA-binds the exact .94 composition receipt, all components, 103 store
paths and 81 SD files. Only cohort.json product version/source revision changes;
102 file contents, every app/provider ELF, Home .4.13, Files 1.5.30, Runtime .2.24,
the .93 minute SD-close transaction, Points, and boot.json stay byte-identical.
All native flash ranges stay identical. Only bootfs and its initial bank-state
digest change. Full-image decoding and digest verification run before output.
The baseline qualification-lock field is explicitly labelled as .94 provenance.

## Pinned filesystem replay

Replay uses ESP-IDF 4.4.7's SPIFFS source
pellepl/spiffs@0dbb3f71c5f6fae3747a9d935372773762baf852, four descriptors,
256-byte pages, 4096-byte blocks, name32/meta4. Every read byte is compared with
the expected extracted file, including all files in randomized order. Mount,
open, fstat, payload and close counts are recorded independently.

- Metadata filename reads: 50,263 -> 193; bytes 11,380,240 -> 36,574.
- Healthy SD first-frame internal filename reads: 52,131 -> 205.
- Cold SD path filename reads: 53,269 -> 1,687.
- Timer fallback filename reads: 54,347 -> 224.
- Full logged foreground fallback filename reads: 64,592 -> 321.
- Randomized all-file filename reads: 78,965 -> 74,444.
- Free blocks: 232, unchanged; occupied blocks: 1,064, unchanged.

These are host HAL operation counts, not device milliseconds or proof of speedup.
Actual .95 hardware timing remains unmeasured. The large first panel refresh is
unchanged. Existing SD-preferred provider selection, Contexts, broadcast cleanup
and dynamic catalog behavior are unchanged.

Normal and ASan/UBSan replay outputs match for seven plans on both images.
Alignment instrumentation is excluded only for the unmodified packed SPIFFS
index-table accesses (UBSan flags the same source line on the baseline image).
Leak detection is unavailable under the execution environment's ptrace and is
disabled. Neither exception changes source or native target code.

`minimal/test/boot_order_095_test.py` validates deterministic packing,
independent decode, unchanged reserve and 23 rejection probes. Exact-native
ELF/import, graph and selected-SD admission must also pass before delivery.

## Reproduction and delivery

Run the .95 test with --baseline pointing to the qualified .94 delivery,
--sd to the existing complete .90 SD tree, --tools to the hash-pinned shared
assembly source, and --runtime to the unchanged .2.24 source. Then run
`compose_boot_order_095.py` with --baseline, --sd, --tools, --runtime-source,
--product-revision set to the exact clean published source and a new --output.
Use the unchanged matching native BIN/ELF for `qualify_installed_catalog.py` with
provider-capacity 40, shared-files, SD and the boot-order composition receipt.
No new executable target build is warranted: its bytes are bound to .94.

Deliver only the raw 16 MiB BIN. No SD overlay is needed. This is a FULL INITIAL
image at offset 0x0 and erases internal settings, saved Wi-Fi and app data.
