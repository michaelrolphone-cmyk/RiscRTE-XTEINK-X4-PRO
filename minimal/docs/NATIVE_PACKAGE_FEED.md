# Native package feed

X4's explicit product catalog repository is `RiskRTE-XTEINK-X4-PRO`.
The old firmware URL names the absent `release-index` branch. Reader's separate
release index contains legacy archive formats and is not a native X4 catalog.
Use `release-index/native-packages-v1.json` for the native App Store feed;
do not substitute it for `release-index.json`, the firmware catalog contract.

`build_native_package_feed.py` consumes explicit application manifest/image
pairs and optional native driver dependency pairs with explicit instances.
It writes schema `riscrte.native-packages`, version 1, product `xteink-x4-pro`.
Each descriptor contains an immutable image name, SHA-256, length, HTTPS URL,
manifest and optional `provider_catalog`. It never creates capability grants
or selects boot drivers. Runtime resolves only missing dependencies and repeats
native admission before publication. Limits are 32 apps, 64 KiB of catalog,
4 KiB per descriptor, eight candidate drivers per app and 2 MiB per image.

Publish checked content-addressed assets first, then generate the final feed
with their immutable Git commit in `--asset-base`. Publish the feed only after
the complete selected product inventory and exact image provenance are checked.
A missing asset or mismatched manifest is a blocker, not permission to use an
older image. Original OBD and OBDTest retain different IDs.

System's installed-app provider must explicitly select `--native-feed` and
the App Store build must select `--native-package-feed` with its installed
catalog. Other products and ordinary provider builds allocate no feed buffer.
The provider performs copied, bounded HTTPS reads and retains ownership after
uncertain close. Catalog snapshots replace atomically; confirmation checks the
catalog generation and package identity again. Network availability never
bypasses RTC validity, immutable image admission or the durable media journal.

`--native-package-volume` selects the complete X4 native settings/mount
composition and scoped package volume in a development native build. Its
workspace uses checked internal-memory allocation so static data cannot
intersect the IQ bank. Allocation failure leaves the capability unpublished.
The final linked IQ proof remains mandatory. This option does not alter .111,
flash a device, format storage or establish hardware qualification.
