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

Remaining: on-device provisioning of a missing provider is not implemented.
The existing native Profile/Coordinator downloads a complete internal store;
Runtime installation metadata admits applications against the already admitted
provider graph. It does not mutate that graph or provision SD driver images.
The offline dependency planner remains planning-only. Completing this requires
the owner-selected catalog/core set/provider bindings, then a staged SD/internal
placement and full-graph activation path with restart/rollback qualification.
The catalog/core/binding selection has been requested and remains unanswered.
Physical SD/panel/power-cut qualification and release assembly also remain.

Darwin host wrappers are included solely for reproducing UBSan checks; they
remove Linux linker flags, allow dynamic host fixture imports, and omit debug
.dSYM sidecars from exact-inventory fixture stores. They are never used in
target builds. Initial unadapted entropy testing rejected the extra .dSYM
directories, then passed with the exact intended fixture inventory.

Final qualification admits all 42 modules. Forward legacy migration from the earlier staged store to the Home migration store admits 39 modules; Home replacement in the already admitted Files-sharing store admits 42. The direct staged-to-Files-sharing policy transition rejects before ELF admission and needs the Files owner’s migration/release procedure; it is not claimed as a passing update path. The optional older Home gesture harness cannot link Darwin weak raster extension symbols; no gesture assertion ran there. The new production Home catalog adapter test passes, including first-frame ordering and 1,000 pending launch/sleep drain polls.
