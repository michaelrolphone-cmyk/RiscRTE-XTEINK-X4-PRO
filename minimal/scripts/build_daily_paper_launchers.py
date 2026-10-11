#!/usr/bin/env python3
"""Rebuild the current X4 Home/Springboard with the additive Daily Paper catalog."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PINS = {'runtime': '7071f0c25e223f24670bed409a5f8b6f291c8042',
        'system': '8ddd9bcf751cecfcf74a67c50c809b87ec75fcc3',
        'utilities': 'e80172353fcb9e6519ca9d9b2a4d43c69c1bc91d'}
HEADERS = {'RiscDisplayOutputV1.h': '99b682ba34f07e7868dec8e78dfb816c067fdc184e647033bc6ed8d489b9c9a2',
           'RiscDisplayOutputPowerV1.h': 'e9c7d3bd3ddf9bce128503aafb5669734db09424149f45b3a6f735cd5a7c8667',
           'RiscTouchPowerV1.h': '82c6faed9b7e26788e3a226cd3532b1d2c3b59447c8abdc25b5e407ef0399dd0',
           'RiscStorageVolumeV1.h': 'd477167a06004640b2c07c05d662c103be6e1b9e4a4d866f6fce13e754ef02f5'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def require(ok, message):
    if not ok:
        raise ValueError(message)

def build(a):
    for name in ('runtime', 'system', 'utilities', 'reader_sdk', 'relocation_tools', 'cc', 'baseline_store', 'output'):
        setattr(a, name, getattr(a, name).resolve())
    for name, pin in PINS.items():
        actual = subprocess.check_output(['git', '-C', str(getattr(a, name)), 'rev-parse', 'HEAD'], text=True).strip()
        require(actual == pin, 'Unexpected source pin: ' + name)
    require(not a.output.exists(), 'Choose a new launcher output directory')
    a.output.mkdir(parents=True)
    sdk = a.output/'sdk'
    sdk.mkdir()
    for folder in (a.reader_sdk, a.runtime/'sdk/app', a.runtime/'sdk/driver',
                   a.runtime/'sdk/hardware', ROOT/'minimal/interfaces'):
        for path in folder.glob('*.h'):
            shutil.copyfile(path, sdk/path.name)
    for name, expected in HEADERS.items():
        require(sha(sdk/name) == expected, 'Canonical SDK mismatch: ' + name)
    catalog = ROOT/'minimal/sd-app-catalog.json'
    apps = json.loads(catalog.read_text())['apps']
    require(len(apps) == 24 and len({r['file_name'] for r in apps}) == 24, 'Catalog must preserve all 23 apps plus Daily Paper')
    require(next(r for r in apps if r['file_name'] == 'daily_digest.elf')['icon'] == 'solid:f15b', 'Use a glyph included in the current licensed subset')
    host = ['--desk-clock', '--sparse-start', '--desk-lock-home', '--desk-points-face',
            '--navigation', '--alarm-client', '--wake-light-restore', '--display-rotation', '90',
            '--local-sleep-source', ROOT/'minimal/apps/portable_sleep.c', '--sleep-capability', 'x4.power',
            '--sleep-sdk', sdk, '--retained-wake-sdk', a.runtime/'sdk/app',
            '--tagged-alarm-utilities', a.utilities, '--paper-crossfade', '--paper-display-sdk', sdk,
            '--paper-transitions', '--quick-actions', '--quick-radios', '--quick-usb-transfer',
            '--resident-shell-host', '--resident-runtime-sdk', a.runtime/'sdk/app', '--ble-broadcast',
            '--x4-idle-source', ROOT/'minimal/apps/portable_idle_sleep.c', '--x4-idle-sdk', sdk,
            '--x4-idle-runtime-sdk', a.runtime/'sdk/driver', '--contexts-rf-only', '--resident-legacy-handoff',
            '--resident-policy', '--resident-loading-catalog', catalog, '--raster-snapshot',
            '--frontlight-tone', '--frontlight-tone-sdk', sdk, '--display-settled-sdk', sdk,
            '--crash-report-sd', '--boot-animation', '--relocation-tools', a.relocation_tools, '--stage-logs']
    spring = ['--resident-shell-client', '--resident-runtime-sdk', a.runtime/'sdk/app',
              '--alarm-client', '--home-app', 'default.elf', '--tagged-alarm-utilities', a.utilities,
              '--native-time-runtime-repo', a.runtime, '--touch-scrolling', '--ble-broadcast',
              '--time-profile', 'x4-native-time', '--catalog', catalog, '--return-app', 'default.elf',
              '--paper-crossfade', '--paper-display-sdk', sdk, '--resident-policy', '--raster-snapshot', '--stage-logs']
    versions = {'default': '0.4.8', 'springboard': '1.7.31'}
    env = dict(os.environ, NATIVE_APP_CC=str(a.cc))
    outputs = {}
    for name, script, args, record in (
            ('default', 'build_paper_clock.py', host, 'build-evidence.json'),
            ('springboard', 'build_portable_springboard.py', spring, 'springboard-build-record.json')):
        target = a.output/name
        command = [sys.executable, a.system/'scripts'/script, *args, '--output-dir', target]
        subprocess.run(list(map(str, command)), check=True, env=env)
        original = json.loads((a.baseline_store/(name+'.json')).read_text())
        manifest = json.loads((target/(name+'.json')).read_text())
        require({k: v for k, v in original.items() if k != 'version'} ==
                {k: v for k, v in manifest.items() if k != 'version'}, name + ' requirements or identity changed')
        old_version = manifest['version']
        manifest['version'] = versions[name]
        (target/(name+'.json')).write_text(json.dumps(manifest, indent=2)+'\n')
        evidence = json.loads((target/record).read_text())
        require(evidence['resident_shell']['role'] == ('host' if name == 'default' else 'foreground'), 'Wrong resident role')
        symbols = subprocess.check_output([str(a.cc).removesuffix('gcc')+'nm', str(target/(name+'.elf'))], text=True)
        definitions = [line.split()[-1] for line in symbols.splitlines() if len(line.split()) >= 3 and line.split()[-2] != 'U']
        require(definitions.count('risc_resident_app_descriptor_v1') == 1, 'Missing resident descriptor')
        require(definitions.count('pqa_render') == (1 if name == 'default' else 0), 'Shared Quick Actions renderer changed')
        evidence.update(version=versions[name], builder_profile_version=old_version,
                        integration='X4 Daily Paper catalog; existing capability requirements preserved')
        (target/record).write_text(json.dumps(evidence, indent=2)+'\n')
        outputs[name] = {'file': name+'.elf', 'version': versions[name], 'bytes': (target/(name+'.elf')).stat().st_size,
                         'sha256': sha(target/(name+'.elf')), 'manifest_sha256': sha(target/(name+'.json')),
                         'command': list(map(str, command)), 'previous_version': original['version']}
    receipt = {'sources': PINS, 'catalog_sha256': sha(catalog), 'catalog': apps, 'built': outputs,
               'sdk_sha256': {p.name: sha(p) for p in sorted(sdk.glob('*.h'))}, 'hardware_tested': False}
    (a.output/'launcher-build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('Home and Springboard target compilation and unchanged requirement checks passed.', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('runtime', 'system', 'utilities', 'reader-sdk', 'relocation-tools', 'cc', 'baseline-store', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    build(parser.parse_args())
