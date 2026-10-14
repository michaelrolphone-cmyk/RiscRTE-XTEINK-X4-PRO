#!/usr/bin/env python3
"""Create bounded X4 native descriptors and immutable, content-addressed assets.

Input: {"apps":[{"manifest":"path", "image":"path", "providers":[
 {"manifest":"path", "image":"path", "instance":0}]}]}.
Paths are relative to the input plan. This does not publish or grant authority.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlparse


def encode(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True).encode()


def build(plan_path, asset_base, output):
    url = urlparse(asset_base)
    if url.scheme != 'https' or not url.netloc or url.query or url.fragment:
        raise ValueError('Assets require a fixed HTTPS base URL')
    plan = json.loads(plan_path.read_text())
    apps = plan.get('apps')
    if not isinstance(apps, list) or not 1 <= len(apps) <= 32:
        raise ValueError('Expected 1..32 apps')
    assets = {}

    def package(row, kind):
        manifest = json.loads((plan_path.parent / row['manifest']).read_text())
        data = (plan_path.parent / row['image']).read_bytes()
        if (len(data) < 52 or len(data) > 2097152 or data[:6] != b'\x7fELF\x01\x01'
                or struct.unpack_from('<H', data, 18)[0] != 94):
            raise ValueError('Expected bounded ELF32 little-endian Xtensa image')
        if manifest.get('type') != kind or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*', manifest.get('id', '')) or '..' in manifest['id']:
            raise ValueError('Invalid package identity')
        if not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', '')):
            raise ValueError('Expected numeric package version')
        digest = hashlib.sha256(data).hexdigest()
        name = 'image-' + digest + '.elf'
        manifest['file_name'] = name
        assets[name] = data
        result = {'manifest': manifest, 'size': len(data), 'sha256': digest,
                  'url': asset_base.rstrip('/') + '/' + name}
        if len(result['url']) > 2048:
            raise ValueError('Asset URL exceeds client bound')
        if kind == 'driver':
            instance = row.get('instance')
            if type(instance) is not int or not 0 <= instance <= 0xffffffff:
                raise ValueError('Driver requires an explicit instance')
            result['instance'] = instance
        return result

    rows = []
    identities = set()
    for app in apps:
        row = package(app, 'application')
        identity = row['manifest']['id']
        if identity in identities:
            raise ValueError('Duplicate application identity')
        identities.add(identity)
        providers = app.get('providers', [])
        if not isinstance(providers, list) or len(providers) > 8:
            raise ValueError('Provider closure exceeds client bound')
        if providers:
            row['provider_catalog'] = [package(p, 'driver') for p in providers]
            keys = [(p['manifest']['id'], p['instance']) for p in row['provider_catalog']]
            if len(set(keys)) != len(keys):
                raise ValueError('Duplicate driver identity and instance')
        if len(encode(row)) > 4096:
            raise ValueError('Descriptor exceeds client bound: ' + identity)
        rows.append(row)
    feed = encode({'schema': 'riscrte.native-packages', 'version': 1,
                   'product': 'xteink-x4-pro', 'apps': rows})
    if len(feed) > 65536:
        raise ValueError('Feed exceeds client bound')
    # Validate the entire plan before creating output; never emit a partial feed.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'assets').mkdir()
    for name, data in assets.items():
        (output / 'assets' / name).write_bytes(data)
    (output / 'native-packages-v1.json').write_bytes(feed)
    receipt = {'schema': 1, 'apps': len(rows), 'assets': len(assets),
               'feed_sha256': hashlib.sha256(feed).hexdigest(),
               'feed_bytes': len(feed), 'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
               'asset_base': asset_base, 'published': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--asset-base', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.plan.resolve(), args.asset_base, args.output)))
