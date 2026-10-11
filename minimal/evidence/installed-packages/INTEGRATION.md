# Dynamic installed packages: integration state

The feature branches implement cached SD discovery, new identity registration,
staged App Store install/update, durable recovery/removal and dormant legacy
authority migration. They include the supplied Files integration commits.
No master merge, release promotion or hardware flash was performed.

The selected native build is Runtime 885d62f + X4 855def7, source composition
7703d3b410494825a6a5015ce802a156b7dcf5ab7f3be7472da32b20c3a79182.
Its explicit selections are 64 apps, 32 providers, 48 graph grants, 24 policy
and requirement rows, native TCP/entropy and the existing IQ/appdata layout.
Native RAM is 78,992 bytes; flash is 1,425,225 bytes.

Selected app/provider artifacts: Home 0.4.9, Springboard 1.8.1, App Store 1.4.0, catalog
0.4.0, SD 0.2.20, Files 1.5.24. Build receipts and complete ELF/store hashes
are recorded in migration-and-sharing.json. This is an admitted development
store, not a flashable or released firmware bundle. Files uses the inherited
explicit development export map; no new user files are authorized for export.

Use compose_installed_catalog.py --migrate-legacy with a Springboard built
using --installed-authority-boot pointing at the exact base boot.json. The
composer refuses a mismatched source-bound compiled catalog. Original SD apps
remain in their existing Apps directories; preserve manifest.json, image and
settings. Their boot records become nonlaunchable authority reservations. Legacy shortcut
filenames resolve only after catalog admission. The migration composer now
requires Home 0.4.9, which hydrates cache and begins discovery only after its
first submitted frame, draining before child launch or sleep.
The cache/discovery decides installation; fixed records preserve existing
private/shared grants. Only eight internal Springboard entries remain compiled;
16 optional appearance records do not enumerate or launch absent apps.

Use System-Apps/scripts/stage_sd_app.py for a new directory or newer package
version. Copy the resulting Apps/<id> folder to SD and select its staged row
in App Store. Existing install.json is a staging offer, not an installed marker.
The worker validates the selected image; a durable internal activation journal
precedes manifest replacement. New images use content-addressed names. Launch
uses ordinary loaded-snapshot structural/import checks, never a catalog scan
or whole-image checksum pass on input. Previous images and settings survive.

The actual Runtime host test adds an SD app after boot configuration, admits
it and executes it twice through the real provider/handoff path. Separate
tests execute the actual catalog, transaction coordinator, copied adapter,
FatFs replacement and native image admission code. Boundary doubles represent
media/native results where stated in their fixtures; none is a hardware run.

Remaining: on-device provisioning of a missing provider is not yet wired.
Runtime 0.2.13 now supports selected SD provider images and copied streamed
package downloads; X4 derives the internal mount closure from the selected
board/boot graph. Use the existing repository catalogs and selected bindings;
no additional owner catalog/core choice is needed. App Store dependency
resolution, durable graph activation and SD-first settings routing remain
implementation work. The checkpoints do not constitute a completed installer.
Physical SD/panel/power-cut qualification and release assembly also remain.

Darwin host wrappers are included solely for reproducing UBSan checks; they
remove Linux linker flags, allow dynamic host fixture imports, and omit debug
.dSYM sidecars from exact-inventory fixture stores. They are never used in
target builds. Initial unadapted entropy testing rejected the extra .dSYM
directories, then passed with the exact intended fixture inventory.

Final qualification admits all 42 modules. Forward legacy migration from the earlier staged store to the Home migration store admits 39 modules; Home replacement in the already admitted Files-sharing store admits 42. The direct staged-to-Files-sharing policy transition rejects before ELF admission and needs the Files owner’s migration/release procedure; it is not claimed as a passing update path. The optional older Home gesture harness cannot link Darwin weak raster extension symbols; no gesture assertion ran there. The new production Home catalog adapter test passes, including first-frame ordering and 1,000 pending launch/sleep drain polls.

### Exact Files transition rejection

The test calls `Runtime::validateCohort(candidate, root, admit, context)` without
native delegations. `validateCohortImpl` calls `validateAppDataExportCohort`. For
`file_browser.json`, the candidate adds `storage.app-data.export@1` and five
non-export grants: `storage.key-value@1` instance 6, `network.tcp.listener@1`,
`crypto.entropy@1`, `net.wifi@1` instance 15 and `bluetooth.session-setup@1`.
The first-map branch rejects these added non-export privileges before selecting
a delegation. Even after a bridge establishes those grants, the ordinary call
with no matching `AppDataExportDelegation` would reject the first map.

Production `NativeBankStore::validateStore` uses `validateNativeCohort` with the
selected `RISC_NATIVE_APP_DATA_EXPORT_POLICY_HEADER`. The missing release inputs
are an operational-grants bridge preserving existing maps, then exact from/to
cohort coordinates (product, version, repository, full source revision, Runtime
version) and the exact consumer/label/owner/namespace/name/path/access delegation.
The development export is timecard namespace 1, `timecard.json`, exposed at
`/timecard/timecard.json` read-write under `Saved files`. Both stores still carry
the old development cohort coordinates, so they are not a ready release pair.
This is a technical Runtime admission condition, not a tool denial or a request
for additional user permission. No admission check was weakened.

### Bridge experiment correction

The operational-grants bridge is insufficient. A diagnostic bridge with the old
Files ELF, a manifest declaring the added operational capabilities, and no export
map prepares successfully but rejects before ELF admission. Removing only the
new Files KV namespace 6 grant admits all 42 ELFs with zero hardware/storage calls.
This isolates a second boundary in `CohortRuntime.inc`: an existing app cannot
expand into a persistent namespace already owned by other principals. Namespace 6
already belongs to Wi-Fi Settings, Update, App Store and Daily Paper. The ordinary
shared-KV migration path explicitly excludes existing-app expansion.

See `files-bridge-diagnosis.json`. The removed-grant variant is diagnostic only;
shipping it would lose saved-Wi-Fi sharing behavior. A complete preserving Files
migration needs an explicit source-bound native shared-KV delegation or a shared
network service retaining credential custody, in addition to the separate exact
export-map policy. This is Runtime admission, not a tool permission rejection.

## Published .84 source checkpoint: SD settings and complete peer store

Runtime 663b6db (0.2.16), System c4ab8d5 (catalog 0.7.0), and X4 9715c5b
compile the native development firmware successfully. Runtime 5c7c296 changes
only a GCC test warning; System 2d4253c recognizes App Store 1.5.0 in the telemetry
builder. The full peer-store composition admits all 42 target modules against
the actual native binary's exports under UBSan with zero hardware/storage
callbacks. See `settings-084.json` for hashes, unchanged peer-file comparison and
negative namespace/settings tests. Reader, Scene, Daily Paper and Files payloads
are byte-for-byte retained from the delivered peer store.

The settings model and real Runtime broker pass restore/readiness, scope denial,
two app launches, journal namespace isolation and existing cohort migrations.
The real catalog/worker passes 65 settings and 110 provider interrupted persistent
states, export exclusion, media removal and cache-only startup. App Store,
Springboard, Home, async SD and catalog target builds pass. The clock sleep fixture
now emits current raw ordered input events; all 28 local cases pass with UBSan
and Darwin-only absent weak raster stubs. No production input logic was changed.

Release boundary: direct preserving admission from the delivered peer store to
this expanded store rejects `missing scoped trusted platform provider`. The
running old graph lacks the new storage-worker native scope. A product-qualified
native-first authority bridge and exact Files export-policy composition are still
required before deployment; self-admission is not an upgrade-path proof. No
master merge, firmware release, SD content publication or hardware flash occurred.
Native provider-catalog descriptors support missing-provider downloads; a public
native package feed is still a deployment input, not the legacy Reader ABI feed.
