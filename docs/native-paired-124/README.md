# X4 0.1.124 paired candidate preparation

This is an additive, unreleased preparation recipe. The .122 and .123 recipes,
release inputs, workflows and artifacts remain frozen. Full native builds run
only in `.github/workflows/native-paired-124.yml`, not on a developer machine.

## Publication gate

The work item permits preparation while the user installs .123, but public
candidate publication waits for explicit installed-bootstrap evidence. This
workflow has `contents: read`, builds/tests only, and uploads temporary Actions
artifacts. It creates no tag or release, changes no Catalog record, and operates
no device. A source draft PR is not a public firmware release. Do not merge or
publish as a side effect of this recipe.

No .124 GitHub release ID, Catalog revision or qualified physical board revision
is invented. `prepare-candidate` emits fixture-marked, NONINSTALLABLE manifest
and container drafts from the actual candidate bytes with a visibly synthetic
release identity. The ordinary validator rejects these drafts for installation.
`finalize` requires actual qualified bytes, exact public-release metadata,
independently collected current Catalog responses, installed .123 evidence and
independently reviewed board/namespace trust context. It only creates local
files; public upload/readback and Catalog association are separate work.

## Exact source and baseline

`source-inputs.json` pins Runtime 6a3b3d46 (0.4.7) and all package/helper sources.
The native toolchain is ESP-IDF 6.1 / GCC 15 in the digest-pinned CI image. Home
is rebuilt with the existing pinned GCC 8 only as an exact-byte regression;
the released Home bytes remain selected. `released-baseline.json` is the
byte-audited .123 factory, including its complete 107-file internal inventory,
43 ELF imports and exact unchanged .121-origin complete SD ZIP of 77 paths.
It does not claim reconstruction of historical retained payload producers.

The new product source SHA and composition hash are embedded in the native
image with `X4_VERSION=0.1.124-paired-candidate`. The build proof records clean
source roots, dependency closure, commands, tools and exact native artifacts.
Detached JSON alone cannot authorize qualification; a fresh controlled build
and package build must remain in the same process.

## Deliberately small payload change

The .123 boot-store path set stays unchanged. Exactly four paths change:

- `installed-apps/driver.elf`: same pinned service implementation, rebuilt for
  the immutable proposed .124 feed URL.
- `installed-apps/manifest.json`: upstream generated service version 0.15.0 is
  retained in its original build receipt; the product feed configuration is
  separately versioned 0.15.1. Qualification records both manifest hashes and
  the configuration source hash. No capabilities are added or removed.
- `boot.json`: only the corresponding content-addressed external service mirror.
- `cohort.json`: exact .124 version, product source and native image binding.

All 103 other internal payloads, Home grants, Settings, provider identities and
partition selections remain unchanged. The new complete SD ZIP retains every
one of the released 77 files byte-for-byte and adds the new service ELF mirror:
78 files, 50 ELFs. The old unused service mirror is retained, never deleted.
Every one of the 49 boot-declared external images is bound to exact payload
bytes; external app manifests must match the internal boot metadata. Fonts and
licenses remain complete resources. Normal and sanitized production loader
admission checks cover all 43 internal and 50 external ELFs.

## Storage and installation semantics

The generic wire namespace is **12**, bound by this product to provider
`x4pro-sd`, storage.volume@1, instance **9**. Wire ID 12 is not provider instance
12. Namespace 1 is immutable active boot storage; namespace 2 is private
scratch appdata, not an installation destination. No boot-store writes or
unsupported rename/delete/format/activation primitives appear in the plan.

The selected combined-update order is **firmware, payload, verify**. The only
selected firmware method is a complete 16 MiB factory image at offset 0.
**It erases internal saved settings and data.** No preserving installer or
OTA kit is emitted. .123-to-.124 cohort admission and inactive-bank byte models
do not establish a preserving flash procedure or bootloader hardware behavior.
External-volume survival is not assumed; payload transfer follows flashing.

Payload source members are portable numbered names, while destinations retain
the exact admitted paths, including font spaces. Parent directories are
created in canonical parent-first order. Every file has explicit create or
replace semantics and exact size/hash; there is no wholesale directory
replacement. Existing files require inspection and an explicit appropriate
plan. CI emits clean-card create, all-present replace, and a mixed fixture plan
assuming all 77 baseline paths exist and the new mirror is absent. None is an
automatic live-card operation selection. Unrelated files must remain untouched. Replacement truncates immediately;
abort/disconnect is not rollback. Lost acknowledgments are uncertain, not a
permission to retry blindly. Complete readback must precede success.

The firmware already supplies the consumer graph; RTEF1 only transfers files.
No new activation primitive is claimed. Physical boot, actual card access,
post-flash connection, consumer use and recovery remain separate hardware work.

## Local controls and CI evidence

Python dependencies: pyelftools 0.32 and jsonschema 4.25.1. CMake is needed for
profile-only host controls. Tests must not write bytecode into clean sources.

```
PYTHONDONTWRITEBYTECODE=1 python tests/test_native_paired_candidate.py \
  --runtime /exact/runtime --image-helper /exact/image-helper \
  --baseline /inputs/factory-candidate-erases-data-0x0.bin \
  --sd-archive /inputs/X4-0.1.121-Complete-SD-Keep-Existing.zip
X4_PAIR_SCHEMA=/exact/schema PYTHONDONTWRITEBYTECODE=1 \
  python tests/test_x4_pair_manifest.py
```

The four schema files are independently hash-checked at frozen Runtime commit
908355b0509907c05a6dc47a1ccc8e078d6e23b0 before importing the validator.
`test_x4_paired_transport.py` uses the pinned actual Python client and C++ RTEF1
endpoint over pipes with a POSIX storage fixture. It transfers and verifies
every file, tests unrelated-file preservation and interruption/uncertain
outcomes, and separately runs actual X4 namespace/provider startup selection.
Its storage fixture uses namespace 1, not physical SD. Neither that fixture nor
host loader admission executes retained Xtensa application/driver instructions.
The retained SD 0.2.23 historical source-rebuild receipt remains unestablished.

CI keeps exact source/build artifacts, qualification and pair-admission receipts,
full inventory/hash records, normal/sanitized transport receipts, noninstallable
manifest drafts and source identities. Build status, source publication,
release publication and hardware testing are distinct evidence states.
