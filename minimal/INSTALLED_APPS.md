
### Async removal interface reservation

The opt-in SD builder now produces 0.2.19 using Runtime's copied async suffix
version 3 (operation 7: idempotent ordinary-file removal). Ordinary/default SD
selection and .80 USB eight-sector batching remain unchanged. Installed-app
provider 0.3.2 uses this operation only after its protected removal journal is
durable. The previous composed checkpoint remains 0.2.18 / catalog 0.3.1 until
new source-bound composition evidence is produced; do not mix these versions
and claim the old receipt qualifies the new removal transaction.
