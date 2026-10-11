#!/usr/bin/env python3
"""Add Daily Paper to a current X4 staging store without rebuilding other apps.

This produces firmware/SD build inputs, not a flashable image. Rebuild Home and
Springboard with sd-app-catalog.json before final packaging. Run ordinary
native/cohort admission and paired-bank packaging on the resulting store.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SD_PATH = 'Apps/daily-digest/daily_digest.elf'
INSTANCES = {'ui.scene': 0, 'file.open': 0, 'storage.volume': 9,
             'runtime.realtime': 0, 'net.wifi': 15, 'storage.key-value': 6,
             'net.http-client': 0}


def policy(boot, manifest):
    """Return an independent additive boot policy. Existing rows stay intact."""
    if manifest['id'] != 'daily-digest' or manifest['file_name'] != 'daily_digest.elf':
        raise ValueError('Wrong application artifact')
    expected = [{'capability': c, 'api': 1} for c in INSTANCES]
    if manifest['requires'] != expected:
        raise ValueError('Application requirements differ from this X4 recipe')
    result = copy.deepcopy(boot)
    rows = result['app_capabilities']
    reader = next((r for r in rows if r['manifest'] == 'ebook_reader.json'), None)
    if not reader or reader.get('image_source', {}).get('volume_instance') != 9:
        raise ValueError('Use the current SD-loaded Reader cohort, not a legacy baseline')
    row = {'manifest': 'daily_digest.json', 'grants': [dict(r, instance_id=INSTANCES[r['capability']]) for r in expected],
           'image_source': {'volume_instance': 9, 'path': SD_PATH}}
    existing = [r for r in rows if r['manifest'] == row['manifest']]
    if existing and existing != [row]:
        raise ValueError('Conflicting existing Daily Paper policy')
    if not existing:
        rows.append(row)
    driver = {'manifest': 'net-http-client/manifest.json'}
    existing = [r for r in result['drivers'] if r['manifest'] == driver['manifest']]
    if existing and existing != [driver]:
        raise ValueError('Conflicting HTTP provider selection')
    if not existing:
        result['drivers'].append(driver)
    foreground = result['resident_shell']['foreground']
    if 'daily_digest.elf' not in foreground:
        foreground.append('daily_digest.elf')
    if 'daily_digest.elf' in result['resident_shell'].get('legacy', []):
        raise ValueError('Daily Paper is a resident foreground app, not a legacy app')
    # The published Runtime 0.2.5 cohort has 28 application/provider slots.
    if len(rows) > 28 or len(result['drivers']) > 28:
        raise ValueError('This cohort exceeds Runtime 0.2.5 capacity; enlarge it before assembly')
    return result


def stage(store, package, output):
    store, package, output = map(Path, (store, package, output))
    if output.exists():
        raise FileExistsError('Choose a new output directory')
    manifest_bytes = (package/'firmware-integration/daily_digest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    boot = policy(json.loads((store/'boot.json').read_text()), manifest)
    provider = package/'firmware-integration/net-http-client'
    provider_manifest = json.loads((provider/'manifest.json').read_text())
    if (provider_manifest['id'] != 'net-http-client' or
        provider_manifest['provides'] != [{'capability': 'net.http-client', 'api': 1}] or
        provider_manifest['requires'] != [{'capability': 'platform.http-client', 'api': 1}]):
        raise ValueError('Wrong HTTP provider package')
    app_bytes = (package/SD_PATH).read_bytes()
    provider_bytes = (provider/'driver.elf').read_bytes()
    for blob in (app_bytes, provider_bytes):
        if blob[:7] != b'\x7fELF\x01\x01\x01' or blob[16:20] != b'\x03\x00\x5e\x00':
            raise ValueError('Expected an Xtensa ELF32 shared module')
    shutil.copytree(store, output/'store')
    (output/'store/boot.json').write_text(json.dumps(boot, indent=2)+'\n')
    (output/'store/daily_digest.json').write_bytes(manifest_bytes)
    shutil.copytree(provider, output/'store/net-http-client', dirs_exist_ok=True)
    target = output/'sd'/SD_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(app_bytes)
    target.with_name('manifest.json').write_bytes(manifest_bytes)
    shutil.copyfile(ROOT/'minimal/sd-app-catalog.json', output/'sd-app-catalog.json')
    (output/'assembly-status.json').write_text(json.dumps({
        'schema': 'x4.daily-paper-staging.v1', 'app_version': manifest['version'],
        'app_count': len(boot['app_capabilities']), 'provider_count': len(boot['drivers']),
        'sd_path': SD_PATH, 'firmware_image_built': False, 'hardware_tested': False,
        'remaining_assembly': ['rebuild Home and Springboard with sd-app-catalog.json',
            'include those launcher binaries and their manifests in the staged store',
            'advance the product/cohort identity for the assembled build',
            'run native ELF and full cohort admission, then paired-bank packaging']
    }, indent=2)+'\n')
    print('Staged Daily Paper app/provider and boot policy; final firmware assembly still required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('store', 'package', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    stage(args.store, args.package, args.output)
