# Shared settings .90 integration

Source reservation only until exact common Runtime/System targets and the final
image pass admission. The checked composer starts from the complete delivered
.89 store and all 76 packaged SD files. It replaces Home, Springboard, Files,
Wi-Fi Settings, and the installed-app catalog with matching rebuilt clients.
It preserves all other files and adds the catalog's immutable SD image.

The initial qualified namespace selection is 1 (general preferences) and 6
(growing Wi-Fi profiles). Other bundled KV namespaces are not claimed as covered
by this product selection. The shared Runtime implementation supports additional
explicit namespaces after their boot/restore behavior has been qualified. HID
pairing identity namespace 10 is not selected.

The target must retain .89's 512-byte native retained-wake allocation, 408-byte
Home snapshot, USB PHY ownership, staged GPIO1 startup, private-AP implementation,
40-provider/64-installed-app capacities, and complete 26-app/32-provider profile.
Files replaces its unused volume-only AppData-export grant with BLE HCI instance
16 for entropy startup. This is an exact 16-grant substitution, not a capacity
increase; mixed/export-root profiles keep their export capability.

Shared reads/writes are BUSY while cold recovery is pending. Home stays runnable
as the restore owner; other apps requiring a selected namespace are refused
before initialization until its RAM state is ready. A refused request is never
left in the launch queue. No launch readiness check reads the SD card.

A successful Wi-Fi Save first confirms the native journal. It is SD-durable only
after the background checkpoint verifies the SD index and closes its worker.
Removing/exporting the card postpones that checkpoint. Full initial flashing
erases internal data; it cannot recover credentials that an older build never
checkpointed to SD. Preserve the card and use a qualified preserving update when
retaining native-only data matters. No device flashing is performed by these
tools.

/RTECFG is excluded from Files, recursive copy, peer operations, and WebDAV.
Recovery records are plaintext. Physical card access and raw USB block export
can expose them; these exclusions are not encryption or a secure-vault claim.
There is no mandatory passphrase or erased-device key. Tests and receipts use
synthetic records and never include real credentials.
