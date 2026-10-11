#!/usr/bin/env python3
"""Derive SD-first provider placement from an already selected complete store.

No catalog guesses, network publication, hardware I/O or authority expansion.
The resulting internal store retains admitted fallback images. SD publication
must be completed before activating its internal boot metadata.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


def prepare(source, output, internal_packages=()):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output or source in output.parents:
        raise ValueError('new output outside source required')
    boot = json.loads((source / 'boot.json').read_text())
    board = json.loads((source / boot['board']).read_text())
    volume = boot['installation']['volume_instance']
    devices = {d['instance_id']: d for d in board['devices']}
    rows = boot['drivers']
    manifests = []
    for row in rows:
        path = Path(row['manifest'])
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError('invalid manifest path')
        manifest = json.loads((source / path).read_text())
        if manifest['type'] != 'driver' or len(manifest['provides']) != 1:
            raise ValueError('ordinary single-capability driver required')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,95}', manifest['id']):
            raise ValueError('invalid package identity')
        manifests.append(manifest)
    edges = [set() for _ in rows]
    native = lambda cap: cap.startswith('platform.') or cap in (
        'hardware.device', 'spi.bus', 'storage.key-value.bound', 'storage.app-data.bound')
    for i, (row, manifest) in enumerate(zip(rows, manifests)):
        device = devices.get(row.get('instance_id'), {})
        bindings = device.get('bindings', {})
        for req in manifest['requires']:
            cap, api = req['capability'], req['api']
            if native(cap):
                continue
            wanted = bindings.get(cap)
            choices = [j for j, m in enumerate(manifests)
                       if m['provides'][0] == {'capability': cap, 'api': api}
                       and (wanted is None or rows[j].get('instance_id') == wanted)]
            if len(choices) != 1:
                raise ValueError(f'no exact selected binding: {manifest["id"]}/{cap}@{api}')
            edges[i].add(choices[0])
    visiting, visited, order = set(), set(), []
    def visit(i):
        if i in visiting:
            raise ValueError('dependency cycle')
        if i in visited:
            return
        visiting.add(i)
        for j in sorted(edges[i]):
            visit(j)
        visiting.remove(i); visited.add(i); order.append(i)
    for i in range(len(rows)):
        visit(i)
    selected = [i for i, row in enumerate(rows) if row.get('instance_id') == volume
                and manifests[i]['provides'] == [{'capability': 'storage.volume', 'api': 1}]]
    if len(selected) != 1:
        raise ValueError('one selected installation volume required')
    internal = set()
    def pin(i):
        if i in internal:
            return
        internal.add(i)
        for j in edges[i]:
            pin(j)
    pin(selected[0])
    # Product recipes pass any exact native-policy package IDs; pin their
    # dependencies too. Runtime independently refuses external native images.
    for package in internal_packages:
        selected = [i for i, m in enumerate(manifests) if m['id'] == package]
        if not selected:
            raise ValueError('unselected internal package: ' + package)
        for i in selected:
            pin(i)
    images = []
    for row, manifest in zip(rows, manifests):
        leaf = Path(manifest['file_name'])
        if len(leaf.parts) != 1 or leaf.suffix != '.elf':
            raise ValueError('invalid image basename')
        image = source / Path(row['manifest']).parent / leaf
        if not image.is_file() or image.is_symlink():
            raise ValueError('regular selected image required')
        blob = image.read_bytes()
        if not blob or len(blob) > 2097152:
            raise ValueError('selected image size out of bounds')
        images.append((image, blob, hashlib.sha256(blob).hexdigest()))
    output.mkdir(parents=True)
    shutil.copytree(source, output / 'store')
    packages = []
    for i in order:
        row, manifest = rows[i], manifests[i]
        image, blob, digest = images[i]
        medium = 'internal' if i in internal else 'sd'
        relative = f'Drivers/{manifest["id"]}/image-{digest}.elf'
        if medium == 'sd':
            dest = output / 'sd' / relative
            dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(blob)
            row['image_source'] = {'volume_instance': volume, 'path': relative, 'internal_fallback': True}
        else:
            row.pop('image_source', None)
        packages.append({'id': manifest['id'], 'version': manifest['version'], 'medium': medium,
                         'instance_id': row.get('instance_id', 0), 'bytes': len(blob), 'sha256': digest,
                         'path': relative if medium == 'sd' else str(image.relative_to(source)),
                         'dependencies': [manifests[j]['id'] for j in sorted(edges[i])]})
    (output / 'store/boot.json').write_text(json.dumps(boot, indent=2) + '\n')
    receipt = {'schema': 'riscrte.sd-first-placement', 'schema_version': 1,
               'base_boot_sha256': hashlib.sha256((source / 'boot.json').read_bytes()).hexdigest(),
               'bootstrap_internal': [manifests[i]['id'] for i in order if i in internal],
               'packages': packages, 'internal_fallback_images_retained': True,
               'activation_requires_complete_sd_publication': True,
               'native_admission_required': True, 'hardware_tested': False}
    (output / 'placement.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--internal-package', action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(prepare(args.store, args.output, args.internal_package), indent=2))
