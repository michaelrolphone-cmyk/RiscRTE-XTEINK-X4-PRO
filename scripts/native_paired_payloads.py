#!/usr/bin/env python3
"""Reviewed .124 payload delta, in-process package custody and frozen feed."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'docs/native-paired-124/source-inputs.json'
CHANGED = {'boot.json', 'cohort.json', 'installed-apps/driver.elf', 'installed-apps/manifest.json'}
HOME_SHA = '08d213f337fc061d63144e25371154679279e3b21a67ba34de30b6a05c98fb26'
_TOKEN = object()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def config():
    return json.loads(CONFIG.read_bytes())


def inventory(root):
    return {p.relative_to(root).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
            for p in sorted(root.rglob('*')) if p.is_file()}


def source_pins(sources):
    import native_paired_candidate as recipe
    return {role: recipe.clean_source(path, recipe.git(path, 'rev-parse', 'HEAD').decode().strip())
            for role, path in sorted(sources.items())}


def check_pins(sources):
    pins = source_pins(sources)
    for role, row in config()['sources'].items():
        require(pins[role]['revision'] == row['revision'], 'Source pin differs: ' + role)
    header = (sources['runtime'] / 'src/ports/esp32s3/NativeSerialStorage.h').read_text()
    require(all(name in header for name in ('RISC_NATIVE_SERIAL_SD_PROVIDER', 'RISC_NATIVE_SERIAL_SD_INSTANCE')),
            'Runtime lacks explicit product-owned serial SD selector; legacy SD12 is forbidden for X4')
    require('bindSd' in (sources['runtime'] / 'src/main.cpp').read_text(),
            'Runtime startup does not use the explicit serial SD admission adapter')
    return pins


class PackageProof:
    pass


def build_packages(sources, output, home_compiler, service_compiler):
    require(not output.exists(), 'Package output must be new')
    pins = check_pins(sources)
    for compiler, version in ((home_compiler, 'esp-2021r2-patch5'), (service_compiler, 'esp-15.2.0_20251204')):
        text = subprocess.check_output([str(compiler), '--version'], text=True)
        require(version in text, 'Wrong package compiler selection')
    cfg = config()
    commands = [
        [sys.executable, sources['system'] / 'scripts/build_home_provision.py',
         '--runtime', sources['runtime'], '--x4', sources['product'],
         '--sdk', sources['reader'] / 'sdk/driver', '--utilities', sources['utilities'],
         '--reader-scripts', sources['reader'] / 'scripts', '--compiler', home_compiler,
         '--output', output / 'home-build'],
        [sys.executable, sources['system'] / 'scripts/build_installed_apps.py',
         '--runtime-repo', sources['runtime'], '--output-dir', output / 'service',
         '--internal-packages', '--native-feed', '--boot-profiles',
         '--feed-product', 'xteink-x4-pro', '--feed-url', cfg['feed_base_url'] + 'native-packages-v1.json',
         '--time-server', cfg['time_server']]]
    from native_idf61_build import clean_environment
    env = clean_environment(sources['sdk'], service_compiler)
    env['NATIVE_APP_CC'] = str(service_compiler)
    for command in commands:
        subprocess.run(list(map(str, command)), env=env, check=True)
    require(source_pins(sources) == pins, 'Package sources changed during target builds')
    proof = PackageProof()
    proof.token, proof.root, proof.pins = _TOKEN, output, pins
    proof.receipt = {'sources': pins, 'commands': [list(map(str, command)) for command in commands],
                     'files': inventory(output), 'compilers': {
                         role: {'path': str(path), 'sha256': sha(path.read_bytes()),
                                'version': subprocess.check_output([str(path), '--version'], text=True).splitlines()[0]}
                         for role, path in (('home-gcc8', home_compiler), ('service-gcc15', service_compiler))},
                     'same_process_build': True, 'hardware_tested': False}
    verify_packages(proof, sources)
    (output / 'package-build-receipt.json').write_bytes(encoded(proof.receipt))
    return proof


def verify_packages(proof, sources):
    require(type(proof) is PackageProof and proof.token is _TOKEN, 'Fresh in-process package build required')
    require(source_pins(sources) == proof.pins, 'Package source closure changed')
    actual = inventory(proof.root)
    actual.pop('package-build-receipt.json', None)
    require(actual == proof.receipt['files'], 'Package output changed after build')
    for row in proof.receipt['compilers'].values():
        require(sha(Path(row['path']).read_bytes()) == row['sha256'], 'Package compiler changed')
    return package_values(proof.root)


def package_values(root):
    """Validate selected package bytes after the caller establishes custody."""
    values = {'default.elf': (root / 'home-build/home/default.elf').read_bytes(),
              'default.json': (root / 'home-build/home/default.json').read_bytes(),
              'installed-apps/driver.elf': (root / 'service/driver.elf').read_bytes(),
              'installed-apps/manifest.json': (root / 'service/manifest.json').read_bytes()}
    require(len(values['default.elf']) == 623060 and sha(values['default.elf']) == HOME_SHA,
            'Home differs from independently reproduced current GCC8 selection')
    evidence = json.loads((root / 'service/build.json').read_bytes())
    cfg = config()
    require(evidence['elf_sha256'] == sha(values['installed-apps/driver.elf']) and
            evidence['service_version'] == '0.15.0' and evidence['internal_packages'] is True and
            evidence['boot_profiles'] is True and evidence['native_feed'] is True and
            evidence['time_server'] == cfg['time_server'] and
            evidence['feed_url'] == cfg['feed_base_url'] + 'native-packages-v1.json' and
            evidence['feed_product'] == 'xteink-x4-pro', 'Wrong catalog build selection')
    manifest = json.loads(values['installed-apps/manifest.json'])
    require(manifest['version'] == '0.15.0', 'Unexpected upstream generated manifest version')
    manifest['version'] = cfg['service_config_version']
    values['installed-apps/manifest.json'] = encoded(manifest)
    return {name: raw for name, raw in values.items() if not name.startswith('default.')}


def manifest_identity(value):
    value = copy.deepcopy(value)
    value.pop('version')
    value['requires'] = sorted(value['requires'], key=lambda row: json.dumps(row, sort_keys=True))
    return value


def expected_boot(before, service):
    boot = json.loads(before['boot.json'])
    homes = [row for row in boot['app_capabilities'] if row['manifest'] == 'default.json']
    require(len(homes) == 1 and len(homes[0]['grants']) == 25, 'Wrong bootstrap Home grants')
    require({'capability': 'storage.key-value', 'api': 1, 'instance_id': 6} in homes[0]['grants'], 'Bootstrap namespace grant missing')
    services = [row for row in boot['drivers'] if row['manifest'] == 'installed-apps/manifest.json']
    require(len(services) == 1, 'Missing/duplicate installed-app service')
    row = services[0]
    require(row['image_source']['volume_instance'] == 9 and row['image_source']['internal_fallback'] is True,
            'Released service volume/fallback differs')
    row['image_source']['path'] = 'Drivers/installed-apps/image-' + sha(service) + '.elf'
    return boot


def preservation_receipt(before, after):
    require(set(before) == set(after), 'Store inventory changed outside reviewed replacement')
    changed = {name for name in before if before[name] != after[name]}
    require(changed == CHANGED, 'Unexpected store changes: ' + str(sorted(changed)))
    require(json.loads(after['boot.json']) == expected_boot(before, after['installed-apps/driver.elf']),
            'Unreviewed boot change or dropped app/provider/settings grant')
    return {'changed': sorted(changed), 'unchanged': {name: sha(raw) for name, raw in sorted(before.items())
                                                    if name not in CHANGED},
            'unchanged_count': len(before) - len(CHANGED),
            'settings_owner_and_writers_unchanged': True,
            'old_grants_preserved': True, 'home_added_wifi_namespace': None,
            'optional_volume_authorized_instance': 9, 'home_volume_selector': 0,
            'baseline_sd_files_unchanged': True, 'hardware_tested': False}


def compose(before, firmware, lock, packages):
    require(set(packages) == CHANGED - {'boot.json', 'cohort.json'}, 'Unexpected package payload')
    service = json.loads(packages['installed-apps/manifest.json'])
    wanted = json.loads(before['installed-apps/manifest.json'])
    require(wanted['version'] == '0.15.0', 'Wrong bootstrap catalog version')
    wanted['version'] = config()['service_config_version']
    require(service == wanted, 'Unreviewed catalog identity/capability delta')
    after = dict(before, **packages)
    # Preserve released manifest ordering for easier auditing.
    after['boot.json'] = encoded(expected_boot(before, packages['installed-apps/driver.elf']))
    cohort = json.loads(before['cohort.json'])
    versions = {v for v in re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]+)', firmware) if v}
    require(versions == {b'0.4.7'}, 'Wrong native Runtime version')
    cohort.update(version='0.1.124', source_revision=lock['sources']['product']['revision'],
                  runtime_version='0.4.7', firmware_size=len(firmware), firmware_sha256=sha(firmware))
    after['cohort.json'] = encoded(cohort)
    preservation_receipt(before, after)
    return after


def write_feed(sources, store, packed, firmware, output):
    cfg = config()
    directory = output / 'store'
    directory.mkdir()
    for name, raw in store.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    command = [sys.executable, sources['system'] / 'scripts/build_boot_profile_feed.py',
               '--runtime', sources['runtime'], '--store', directory,
               '--image', output / 'store.bin', '--firmware', output / 'firmware.bin',
               '--output', output / 'feed', '--base-url', cfg['feed_base_url'],
               '--product', 'xteink-x4-pro', '--profile', 'core',
               '--time-server', cfg['time_server'], '--mirror-volume-instance', '9']
    subprocess.run(list(map(str, command)), check=True)
    receipt = json.loads((output / 'feed/receipt.json').read_bytes())
    require(receipt['published'] is False and receipt['credential_free'] is True, 'Unsafe feed receipt')
    return {'base_url': cfg['feed_base_url'], 'catalog_url': cfg['feed_base_url'] + 'native-packages-v1.json',
            'command': list(map(str, command)), 'receipt': receipt, 'files': inventory(output / 'feed'),
            'publication_enabled': False}


def external_consumers(store, files):
    """Bind every product boot external image and paired app manifest to SD bytes."""
    boot=json.loads(store['boot.json']); admitted=[]
    for category in ('app_capabilities','drivers'):
        for row in boot.get(category,[]):
            source=row.get('image_source')
            if not source: continue
            require(source['volume_instance']==9, 'Unexpected external consumer volume')
            path=source['path']
            require(path in files, 'Missing exact external consumer: '+path)
            addresses=re.findall(r'image-([0-9a-f]{64})',path)
            require(not addresses or addresses==[sha(files[path])], 'External content-address mismatch: '+path)
            manifest=row['manifest']
            if category=='app_capabilities':
                destination=str(Path(path).parent/'manifest.json')
                require(destination in files and files[destination]==store[manifest], 'External app manifest mismatch: '+destination)
            admitted.append({'path':path,'manifest':manifest,'bytes':len(files[path]),'sha256':sha(files[path]),'volume_instance':9})
    return admitted


def complete_sd(baseline_files, store, baseline_contract):
    """Retain all released paths and add the exact new optional service mirror."""
    import copy, io, zipfile
    require(len(baseline_files) == 77, 'Complete released SD inventory required')
    rows = [r for r in json.loads(store['boot.json'])['drivers'] if r['manifest'] == 'installed-apps/manifest.json']
    require(len(rows) == 1, 'Ambiguous catalog consumer')
    binding = rows[0]['image_source']
    require(binding['volume_instance'] == 9 and binding['internal_fallback'] is True, 'Catalog consumer mapping changed')
    name = binding['path']; data = store['installed-apps/driver.elf']
    require(name == 'Drivers/installed-apps/image-' + sha(data) + '.elf' and name not in baseline_files, 'New exact catalog mirror required')
    files = dict(baseline_files, **{name: data})
    target = copy.deepcopy(baseline_contract)
    target['sd']['file_count'] = 78; target['sd']['elf_count'] = 50
    target['sd']['files'][name] = {'bytes': len(data), 'sha256': sha(data), 'role': 'driver'}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as z:
        for path, raw in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(1980,1,1,0,0,0)); info.create_system=3; info.external_attr=0o100644 << 16
            z.writestr(info, raw)
    consumers=external_consumers(store, files)
    inventory = {n: {'bytes': len(v), 'sha256': sha(v), 'role': target['sd']['files'][n]['role']} for n,v in sorted(files.items())}
    return output.getvalue(), files, target, {'baseline_file_count': 77, 'baseline_files_unchanged': True,
        'added_paths': [name], 'external_consumers':consumers, 'file_count': 78, 'elf_count': 50, 'files': inventory,
        'unrelated_files_deleted': False, 'hardware_tested': False}
