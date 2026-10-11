# X4 .90 recovery integration and unfinished persistence

Source reservation only until exact common Runtime/System targets and the final
image pass admission. The checked composer starts from the complete delivered
.89 store and all 76 packaged SD files. It replaces Home, Springboard, Files,
Wi-Fi Settings, the installed-app catalog, and Contexts with matching rebuilt clients. Contexts 0.4.2 combines the delivered learning-completion behavior with crown cleanup; its RF-only service stays byte-identical to .89.
It preserves all other files and adds the catalog's immutable SD image. It also
adds matching immutable copies of the delivered internal Wi-Fi and BLE session
providers and retargets their preferred SD paths: .89 selected older SD images
for those two providers. All 76 old packaged SD files remain byte-identical.
Contexts uses a new immutable SD directory containing its ELF and matching manifest, while its original files remain intact. The final overlay adds five files.
The .90 SD overlay is required; the old .89 SD package alone is insufficient.

Shared settings are NOT enabled in .90. General preferences, Wi-Fi profiles and
other bundled KV namespaces retain their native behavior. The experimental
Runtime routing and client support remain available for further development, but
its cold-card requirement does not satisfy usable fallback when SD is absent. A
durable native replica and safe returning-card reconciliation must qualify before
product opt-in. HID pairing identity namespace 10 is also not selected.

The target must retain .89's 512-byte native retained-wake allocation, 408-byte
Home snapshot, USB PHY ownership, staged GPIO1 startup, private-AP implementation,
40-provider/64-installed-app capacities, and complete 26-app/32-provider profile.
Files replaces its unused volume-only AppData-export grant with BLE HCI instance
16 for entropy startup. This is an exact 16-grant substitution, not a capacity
increase; its unused export projection is removed with the grant. Mixed/export-root
profiles keep their export capability.

In the disabled experimental mode, shared reads/writes are BUSY while cold
recovery is pending. Home stays runnable
as the restore owner; other apps requiring a selected namespace are refused
before initialization until its RAM state is ready. A refused request is never
left in the launch queue. No launch readiness check reads the SD card.

.90 does not newly back up bundled settings or Wi-Fi profiles to SD. A successful
Wi-Fi Save confirms native storage only. The experimental SD mode checkpoints
after verified index replacement and worker close, but remains disabled. Full initial flashing
erases internal data; it cannot recover credentials that an older build never
checkpointed to SD. Preserve the card and use a qualified preserving update when
retaining native-only data matters. No device flashing is performed by these
tools.

/RTECFG is excluded from Files, recursive copy, peer operations, and WebDAV.
Recovery records are plaintext. Physical card access and raw USB block export
can expose them; these exclusions are not encryption or a secure-vault claim.
There is no mandatory passphrase or erased-device key. Tests and receipts use
synthetic records and never include real credentials.
