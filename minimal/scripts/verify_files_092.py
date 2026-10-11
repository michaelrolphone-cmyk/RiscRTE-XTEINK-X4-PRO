#!/usr/bin/env python3
"""Read back a Files-only .92 BIN against pinned inputs with the SPIFFS decoder.

Does not build or modify an image. Verifies the complete flash preservation
ranges, decoded store, bank-state CRC/digests, and the unchanged .90 SD inventory.
"""
import argparse
import json
from pathlib import Path
from compose_files_092 import (ALLOWED, BANK_STATE, BOOTFS, FILES_LOCK, FILES_NAMES,
    IMAGE_NAME, VERSION, baseline, changed_store, inventory, load_assembly_tools,
    require, sha, verify_image)


def verify(a):
    _, _, old, sd, base_full, components, _ = baseline(a.baseline)
    lock = json.loads(FILES_LOCK.read_bytes())
    artifacts = {name: (a.output / 'receipts/files-client' / name).read_bytes() for name in FILES_NAMES}
    require(inventory(artifacts) == lock['artifacts'], 'Files input artifacts differ from lock')
    receipt = json.loads((a.output / 'receipts/files-composition.json').read_bytes())
    require(receipt['product_version'] == VERSION and receipt['files_lock_sha256'] == sha(FILES_LOCK.read_bytes()),
            'Composition source lock differs')
    expected = changed_store(old, artifacts, receipt['product_source'])
    _, read_image, _, parse_record = load_assembly_tools(a.tools, a.runtime_source)
    full = (a.output / IMAGE_NAME).read_bytes()
    proof = verify_image(full, base_full, old, expected, components, read_image, parse_record)
    for key, value in proof.items():
        require(receipt[key] == value, 'Composition verification receipt differs: ' + key)
    require(receipt['store'] == inventory(expected) and receipt['sd'] == inventory(sd) and
            receipt['original_sd_files_preserved'] == len(sd) == 81 and receipt['added_sd_files'] == [] and
            receipt['sd_overlay_required'] is False and receipt['sd_deliverable_created'] is False and
            not (a.output / 'SD').exists(), 'SD/store preservation receipt differs')
    store = {}
    for path in (a.output / 'store').rglob('*'):
        require(not path.is_symlink(), 'Store evidence contains symlink')
        if path.is_file():
            store[path.relative_to(a.output / 'store').as_posix()] = path.read_bytes()
    require(store == expected, 'Staged store differs from independently decoded full image')
    components = dict(components, **{'bootfs.bin': full[slice(*BOOTFS)], 'bank_state.bin': full[slice(*BANK_STATE)]})
    require({p.name for p in (a.output / 'components').iterdir()} == set(components), 'Component evidence set differs')
    for name, raw in components.items():
        require((a.output / 'components' / name).read_bytes() == raw and
                receipt['components'][name]['sha256'] == sha(raw) and
                receipt['components'][name]['bytes'] == len(raw), 'Component evidence differs: ' + name)
    return dict(**proof, original_sd_files_preserved=81, added_sd_files=[], sd_deliverable_created=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'output', 'tools', 'runtime-source'):
        p.add_argument('--' + name, required=True, type=Path)
    print(json.dumps(verify(p.parse_args()), indent=2))


if __name__ == '__main__':
    main()
