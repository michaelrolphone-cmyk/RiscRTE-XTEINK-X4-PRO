
### Async removal interface reservation

The opt-in SD builder now produces 0.2.19 using Runtime's copied async suffix
version 3 (operation 7: idempotent ordinary-file removal). Ordinary/default SD
selection and .80 USB eight-sector batching remain unchanged. Installed-app
provider 0.3.2 uses this operation only after its protected removal journal is
durable. The previous composed checkpoint remains 0.2.18 / catalog 0.3.1 until
new source-bound composition evidence is produced; do not mix these versions
and claim the old receipt qualifies the new removal transaction.

The in-progress staged-install lane reserves opt-in SD 0.2.20. It appends package
operations through the separately tagged package suffix, keeping async v3 and
operations 1–7 unchanged. Runtime 0.2.9 supplies worker-only native admission.
No provider-capacity edits are included; Files/WebDAV integration remains a
separate composition task. Full install/update qualification is not yet claimed.

### Source checkpoint: Runtime 0.2.16 / catalog 0.7.0

The development .84 lane is distinct from delivered .83/Watch 1.1.4. Runtime
663b6db and System Apps c4ab8d5 add selected missing-provider closure and explicit
SD-first private KV checkpoints. The CI pins include the combined canonical SD
and BLE Drivers 39b9be0. The Files owner's migration remains the only shared
export-map mechanism; this lane does not change its namespace ownership.

Local UBSan passes: actual dynamically registered SD application/provider launch,
KV broker readiness and private scope, 65 settings restart cuts, 110 provisioning
restart cuts, native journal isolation, cohort migration and catalog/App Store
regressions. The standalone target catalog links. Complete exact .84 native/store
qualification is still in progress; no hardware, release, master merge or flash
has occurred. Private KV is limited to 16 keys per installed namespace. AppData,
shared settings and Wi-Fi storage are unchanged.
