# X4 0.1.123 provisioning and generic serial candidate

This is an additive, unpublished candidate. The released 0.1.122 profile,
producer, transport, source lock, settings owner/writers and partition map remain
byte-identical. No native build or hardware execution is claimed by this source
checkpoint. The exact-source GitHub workflow owns the full native build.

## Reviewed replacement

The input is the verified published 0.1.122 16 MiB factory, SHA-256
`bc7e913dff34a4a82b455f3eddac910d45e7201a4ded19d372b2a8fd54a30d10`.
The new baseline inventory is recovered from those actual bytes, not inferred
from a historical build. Only these six internal files may change:

- `default.elf` and `default.json`: Home 0.4.19 to 0.4.20, current GCC8 sparse
  automatic-provisioning selection. All 21 manifest requirements remain.
- `installed-apps/driver.elf` and `installed-apps/manifest.json`: catalog service
  0.9.0 to 0.15.0, internal package volume, native boot-profile feed and private
  first-fetch clock. Only its two reviewed platform requirements are added.
- `boot.json`: preserve all existing app/provider/settings policies; add Home's
  missing Wi-Fi namespace 6 grant and update only the catalog service's
  content-addressed SD9 mirror path. Home has 25 grants; the existing supported
  native bound is explicitly 32 policy slots, with 24 requirement slots.
  The preserved native platform graph requires 34 registered tables, so this
  product explicitly selects 40 platform slots. Runtime's default stays 32.
- `cohort.json`: exact new product/Runtime/native image binding.

The other 101 internal files, including retained Settings 1.3.29, remain exactly
unchanged. The original complete SD ZIP is delivered unchanged, under its own
0.1.121 name and digest. Its old service image may remain unused on a card; the
new boot row falls back to the new internal service until the matching immutable
mirror exists. No package installation deletes unrelated card files.

The native profile selects `RISC_NATIVE_PROVISION_REQUEST=1`. Home uses the
authoritative optional-volume selector 0; its existing grant remains SD9.
Provisioning respects foreground/radio policy and uses saved credentials through
the guarded adapter. Neither its private first-fetch time nor this composition
changes RTC behavior. Retained Settings first-save qualification is separate.

## Generic serial boundary

RTEF1 selects the generic endpoint, a read-only active boot view, a writable
`/appdata/.serial-files` directory, and an explicit SD provider binding:
`x4pro-sd` instance 9. Wire namespace 12 and provider instance 9 are separate
identities. There is no catalog, package, manifest or firmware-flashing policy in
RTEF1. Ordinary file writes preserve unrelated paths. The candidate fails closed
if the pinned Runtime still has the legacy hard-coded SD12 binding.

Runtime `3d9766892331f264601251e811ef06f7838ddf4a` contains the product-owned
selector and its production startup tests. CI runs the actual Runtime startup
suite normally and with ASan/UBSan, preserving both receipts. Qualification
requires and hash-locks their exact command/source identities, both X4SD9 and
legacyWave12 profiles, all 13 scenarios per profile and ten rejected selector
configurations. Missing, changed, wrong-source or unsanitized receipts fail
closed. These tests use synthetic storage; they do not qualify the retained X4
driver or physical hardware. Final native compile definitions and linked
workspace placement are separate required gates.

The 43-ELF admission fixture separately prepares the actual candidate graph and
calls production `NativeSerialStorage::bindSd` with retained `sd/driver.elf` and
`sd/manifest.json` (x4pro-sd 0.2.23, instance 9). Its SD-only namespace 12 must be
selected while its provider session remains unbound and native hardware/storage
counters remain zero. The fixture explicitly admits its host metadata roots;
there is no ambient filesystem fallback. Both normal and sanitized admission
receipts include the retained ELF/manifest hashes. This proves graph selection
and target ELF admission without acquiring a provider grant, executing target
instructions, mounting media or testing physical hardware. Historical source
build provenance of that retained ELF remains unestablished.

Final qualification checks the allocated `risc_platform_capacity` marker for
40, verifies matching compile definitions and records native linked RAM margins.
The default32/explicit40 Runtime regression exercises exact registration and
complete preparation limits normally and with ASan/UBSan. No platform is dropped
to fit the graph, and capacity selection does not grant new authority.

## Build and evidence

`source-inputs.json` locks all dependency revisions and the single feed base:

https://github.com/michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO/releases/download/test-native-provision-0.1.123/

The product itself is the exact event commit, not a mutable branch checkout.
SDK6.1 and its container digest are pinned. Home uses the delivered GCC8 compiler;
resident Runtime and catalog service use pinned GCC15. Full native builds run
only in GitHub CI. The same process builds both packages, captures tool/source
and output hashes, performs a fresh one-job native build, checks dependency
custody, binds the final ELF/BIN, and runs production 43-internal/49-SD ELF
admission normally and with sanitizers. Detached receipts cannot authorize output.
The final report includes native RAM section placement/margins, GPIO1/startup,
bootlog/IQ, and external serial workspace placement.

The credential-free feed generator consumes only the qualified final store and
firmware. `--mirror-volume-instance 9` verifies the one admitted volume and every
fallback mirror without rewriting grants. The catalog is `native-packages-v1.json`;
assets are `bootfs-<sha256>.bin` and `image-<sha256>.elf`. Feed bytes, all assets,
package outputs, complete source/SDK snapshots, original release inputs and full
native build evidence are retained. Publication is disabled in this workflow.

CI publishes three readback artifacts: `qualification` contains only reports,
startup receipts and logs; `candidate` contains delivery assets; `reproducibility`
retains the complete source/SDK snapshots, inputs and native/package build trees.
The small qualification artifact can be inspected without downloading SDK/build
archives. All three names include the exact product commit.

## Delivery and installation limits

The generated factory is explicitly named
`factory-candidate-erases-data-0x0.bin`: flashing it erases internal saved data.
Its unchanged partition geometry does not make factory flashing non-erasing.
The offline preservation model checks NVS, app-data, inactive-bank ordering,
unassigned flash and trailing bytes; it is not hardware evidence or an installer.
No preserving flash kit is emitted and no device is accessed.

After qualification, this candidate may serve as the initial bootstrap with its
accurate erasure warning. Any subsequent firmware/full-payload paired release
must wait for confirmed user installation of that bootstrap. Source/host success,
a complete CI candidate, publication and installed-device verification are
separate gates.

The exact selected native compile database also produces two bounded Runtime
size/allocation probes (capacity 32 and 40). Their source, target objects and
receipt are frozen in controlled build evidence. Qualification rechecks their
commands, compiler/source hashes, Xtensa ELF symbol sizes and +960-byte delta.
The allocation is the existing paired `NativeRuntime` PSRAM-only retained object;
it does not fall back to internal heap. These object measurements do not replace
the final linked memory/IQ proof or hardware heap measurements.
