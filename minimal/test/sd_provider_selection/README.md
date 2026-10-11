# X4 private-radio selected-byte regression

Pinned Runtime: `3b90cd11cf0ff4e8116bb54d2d9eb9c7c67a148b`.
No production source is edited. Run with:

```
RUNTIME_SOURCE=/path/to/exact/Runtime ./run.sh /path/to/delivered-089 /path/to/composed-090
SANITIZE=1 BUILD_DIR="$PWD/build-sanitized" RUNTIME_SOURCE=/path/to/exact/Runtime ./run.sh /path/to/delivered-089 /path/to/composed-090
```

Both product directories must contain `store/boot.json`, the internal `store/`
provider files and their `SD/` image trees. Only the proof build directory is
written. Each run emits `receipt.json` there.

The harness compiles the actual Runtime, GraphV2, ModuleV2, removable-image
snapshot path, and production Xtensa ELF structural validator. It copies the
exact product `image_source.path`, volume instance and fallback selection into
a minimal independently admitted provider graph. The fixture SD provider reads
the real product bytes in bounded 333-byte chunks. At the native reader boundary
it asserts all media handles are closed and the complete selected snapshot is
byte-for-byte equal to the expected delivered image. The internal fallback is
likewise intercepted only after the actual Runtime selection and checked in
full. The final Xtensa machine-code execution is substituted by a host provider;
this proof does not execute Wi-Fi or Bluetooth firmware and does not qualify
physical hardware. Full product metadata admission is a separate assembly test.

For each Wi-Fi and BLE setup provider, six cases check:
- The old selected SD image really shadows the newer internal image.
- With the old policy and absent card, the current internal image is selected.
- The updated immutable SD path selects current bytes while the old image exists.
- An absent card selects the current internal image.
- A missing selected file selects the current internal image, not the old SD path.
- A corrupted selected file is structurally rejected and falls back to current
  internal bytes, not the old SD path.

The runner checks the current SD filename's SHA-256, equality with the intended
internal fallback, retention of the old SD image and expected private-radio
contract symbols. Byte equality binds selection to the assembly's qualified
provider artifact; symbol checks do not substitute for behavioral provider tests.

On the current traced cloud execution environment, LeakSanitizer exits with
`LeakSanitizer does not work under ptrace`. The recorded sanitized run therefore
uses `ASAN_OPTIONS=detect_leaks=0`: AddressSanitizer and UndefinedBehaviorSanitizer
remain enabled, but leak detection is not qualified here. Use the same option to
reproduce in this environment, or leave it unset on an ordinary CI runner.
