#!/usr/bin/env python3
"""Reviewed .123 payload delta, in-process package custody and frozen feed."""
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
CONFIG = ROOT / 'docs/native-provision-123/source-inputs.json'
CHANGED = {'boot.json', 'cohort.json', 'default.elf', 'default.json',
           'installed-apps/driver.elf', 'installed-apps/manifest.json'}
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
    import native_provision_candidate as recipe
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
    values = {'default.elf': (proof.root / 'home-build/home/default.elf').read_bytes(),
              'default.json': (proof.root / 'home-build/home/default.json').read_bytes(),
              'installed-apps/driver.elf': (proof.root / 'service/driver.elf').read_bytes(),
              'installed-apps/manifest.json': (proof.root / 'service/manifest.json').read_bytes()}
    require(len(values['default.elf']) == 623060 and sha(values['default.elf']) == HOME_SHA,
            'Home differs from independently reproduced current GCC8 selection')
    evidence = json.loads((proof.root / 'service/build.json').read_bytes())
    cfg = config()
    require(evidence['elf_sha256'] == sha(values['installed-apps/driver.elf']) and
            evidence['service_version'] == '0.15.0' and evidence['internal_packages'] is True and
            evidence['boot_profiles'] is True and evidence['native_feed'] is True and
            evidence['time_server'] == cfg['time_server'] and
            evidence['feed_url'] == cfg['feed_base_url'] + 'native-packages-v1.json' and
            evidence['feed_product'] == 'xteink-x4-pro', 'Wrong catalog build selection')
    return values


def manifest_identity(value):
    value = copy.deepcopy(value)
    value.pop('version')
    value['requires'] = sorted(value['requires'], key=lambda row: json.dumps(row, sort_keys=True))
    return value


def expected_boot(before, service):
    boot = json.loads(before['boot.json'])
    homes = [row for row in boot['app_capabilities'] if row['manifest'] == 'default.json']
    require(len(homes) == 1 and len(homes[0]['grants']) == 24, 'Wrong released Home grants')
    grant = {'capability': 'storage.key-value', 'api': 1, 'instance_id': 6}
    require(grant not in homes[0]['grants'], 'Wi-Fi namespace already selected unexpectedly')
    homes[0]['grants'].append(grant)
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
            'old_grants_preserved': True, 'home_added_wifi_namespace': 6,
            'optional_volume_authorized_instance': 9, 'home_volume_selector': 0,
            'sd_archive_unchanged': True, 'hardware_tested': False}


def compose(before, firmware, lock, packages):
    require(set(packages) == CHANGED - {'boot.json', 'cohort.json'}, 'Unexpected package payload')
    home = json.loads(packages['default.json'])
    old_home = json.loads(before['default.json'])
    require(old_home['version'] == '0.4.19' and home['version'] == '0.4.20' and
            manifest_identity(home) == manifest_identity(old_home), 'Unreviewed Home identity/capability delta')
    service = json.loads(packages['installed-apps/manifest.json'])
    wanted = json.loads(before['installed-apps/manifest.json'])
    require(wanted['version'] == '0.9.0', 'Wrong released catalog version')
    wanted['version'] = '0.15.0'
    wanted['requires'] += [{'capability': 'platform.provision-request', 'api': 1},
                           {'capability': 'platform.package-volume', 'api': 1}]
    require(service == wanted, 'Unreviewed catalog manifest delta')
    after = dict(before, **packages)
    # Preserve released manifest ordering for easier auditing.
    after['default.json'] = encoded(dict(old_home, version='0.4.20'))
    after['boot.json'] = encoded(expected_boot(before, packages['installed-apps/driver.elf']))
    cohort = json.loads(before['cohort.json'])
    versions = {v for v in re.findall(rb'RISC_RUNTIME_VERSION:([^\x00]+)', firmware) if v}
    require(versions == {b'0.4.7'}, 'Wrong native Runtime version')
    cohort.update(version='0.1.123', source_revision=lock['sources']['product']['revision'],
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
