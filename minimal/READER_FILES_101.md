# X4 0.1.101: Reader and Files regressions

Delivered 2026-10-12 at 11:16:58 UTC. Frozen BIN and changed-SD hashes, source
mapping and qualification are in `reader-files-101-qualified.json`.

## Repairs

- Files 1.5.32: the successful file-open path had already closed Files and set
  terminal state, but the final display drain rejected the finished setup
  service and retained the entire invocation. The actual application-loop
  regression fails before the correction and passes after it. No-work clean
  terminal states are accepted; live or failed cleanup still fails closed.
- Files keeps scroll contact/kinetic movement active across resident-policy
  checks, preserving release fling and visible offset.
- Reader 0.1.9 indexes `/Books` recursively. Stale whole-card index rows and
  outside recent paths are excluded before loading their summaries. Explicit
  Browse SD and Files Open still support arbitrary readable SD paths.
- Reader preserves its current scene, scroll offset and rendered rows during
  idle/power policy checkpoints. Browse SD lists copied directory entries
  directly rather than opening every file merely to list it.

The submitted log identifies Runtime .28 (`1c1ed866`), successful Files
termination and invocation retention before Reader entry. It contains no
Reader load or CPU panic. Because .99 and .100 share native Runtime and Reader
bytes, the native source marker alone cannot distinguish those two products.

## Qualified and preserved

Normal and ASan/UBSan checks admit all 43 internal and 48 selected SD images,
including exact OBD and Hollow native catalog paths. Focused real-app tests
cover idle policy with retained scroll, `/Books` scope, outside Browse/Open,
Files terminal handoff and active scroll release. Reader engine, GUI, links,
file checkpoint and post-policy page performance pass. Target ELF admission
and bounded Reader stack-frame checks pass. Physical hardware is untested.

The native firmware, partition map, boot authority, capability bindings,
accepted startup ordering, SD application lifecycle, Home, OBD, HTTPS/Hollow
and shared scene/text keyboard provider pair are unchanged from .100.
Book-page full CLEAN refresh behavior remains intact.

Only four internal paths change: Files ELF/manifest, Reader manifest and
cohort provenance. The SD overlay changes Reader ELF/manifest and carries the
seven existing cumulative .100 overlay entries. Merge its nine paths into an
existing .96-or-later card, retaining all other files. The full initial BIN
is explicitly an internal-data-erasing image.

## Source and reproduction

The urgent delivery was built from clean committed sources while GitHub
publication was awaiting renewed approval. Published commits have exactly the
same source trees; the mapping receipt records both identities. A restorable
private work-unit archive includes the original Git objects and build inputs.

`compose_reader_files_101.py` verifies the exact frozen .100 image, all source
and artifact hashes, unchanged manifests/grants/profile, accepted packing,
independent SPIFFS decode, paired-bank authentication, selected SD graph and
full readback. Its later source-identity update also accepts the exact-tree
published Files commit. `qualify_reader_files_101.py` runs the full native
admission/catalog suite in normal and sanitizer modes.

No later documentation/source-publication update replaces the delivered BIN
or silently changes its recorded SHA-256.
