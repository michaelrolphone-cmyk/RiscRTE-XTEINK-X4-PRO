#!/usr/bin/env python3
"""Offline Files-only .92 image from the exact delivered .90 archives.

Keeps the delivered native firmware, boot authority, all providers and SD bytes.
Only the internal Files ELF/manifest and cohort version/provenance change.
No device access, network, publication, SD deliverable or preservation claim.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE_RECEIPT = ROOT / 'minimal/recovery-090-qualified.json'
FILES_LOCK = ROOT / 'minimal/files-092-inputs.json'
PRODUCT_BASE = 'c8004c5c8362b142ebb35a0e1c5d266532a11581'
RUNTIME = '3b90cd11cf0ff4e8116bb54d2d9eb9c7c67a148b'
SYSTEM = '1aaf53e23ca9651a5cf9d1debe44941c9d7d0e58'
SYSTEM_TREE = 'df34bc79caeee0815230d2a35ec1995606ec66d6'
VERSION = '0.1.92'
FILES_VERSION = '1.5.30'
IMAGE_NAME = 'X4-0.1.92-FULL-INITIAL-ERASES-DATA.bin'
FILES_NAMES = ('file_browser.json', 'file_browser.elf', 'file_browser-build-record.json')
ALLOWED = {'cohort.json', 'file_browser.json', 'file_browser.elf'}
TOOL_HASHES = {
    'scripts/current_bootfs.py': '3f902ef317e6a112be6b3496d2d6c9cd07376941baa61804b99cadaceb6f798a',
    'scripts/read_only_spiffs.py': 'f50729234cd7f5efc3406cc9737a66e097e0de763df2f3c5efc148ab8c4674c6',
    'vendor/esp-idf-spiffs/spiffsgen.py': '5779792a4d98a12383233267511735769a201b5c2c79b582186a40c22b7c6466',
}
BANK_TOOL_HASH = 'dc26281b1f3476236f904e5051c2c52f69d207faafdbd6283b50bd2184a4cfbb'
BOOTFS = (0x2f0000, 0x800000)
BANK_STATE = (0xff2000, 0xff4000)
PRESERVED_FLASH = ((0, BOOTFS[0]), (BOOTFS[1], BANK_STATE[0]), (BANK_STATE[1], 0x1000000))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def inventory(files):
    return {name: sha(raw) for name, raw in sorted(files.items())}


def safe_name(name):
    p = PurePosixPath(name)
    require(bool(name) and '\x00' not in name and '\\' not in name and
            not p.is_absolute() and '..' not in p.parts and str(p) == name,
            'Unsafe relative path: ' + name)
    return p


def write_files(root, files):
    for name, raw in files.items():
        safe_name(name)
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def archive(path, expected):
    raw = path.read_bytes()
    require(len(raw) == expected['bytes'] and sha(raw) == expected['sha256'],
            'Not the exact delivered archive: ' + path.name)
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive member')
        require(z.testzip() is None, 'Archive checksum failure')
        result = {}
        for info in z.infolist():
            safe_name(info.filename.rstrip('/') if info.is_dir() else info.filename)
            require((info.external_attr >> 16) & 0o170000 != 0o120000,
                    'Archive symlinks are forbidden')
            if not info.is_dir():
                result[info.filename] = z.read(info)
        return result


def select(files, prefix):
    return {name[len(prefix):]: raw for name, raw in files.items() if name.startswith(prefix)}


def baseline(folder):
    receipt = json.loads(BASE_RECEIPT.read_bytes())
    suffixes = ('Recovery-Full-Image', 'Evidence-and-Components', 'SD-Overlay-Keep-Existing')
    archives = {s: archive(folder / ('X4-0.1.90-' + s + '.zip'),
                          receipt['artifacts']['X4-0.1.90-' + s + '.zip']) for s in suffixes}
    evidence = archives['Evidence-and-Components']
    store = select(evidence, 'store/')
    sd = select(archives['SD-Overlay-Keep-Existing'], 'SD/')
    full = archives['Recovery-Full-Image']['X4-0.1.90-FULL-INITIAL-ERASES-DATA.bin']
    components = select(evidence, 'components/')
    original = json.loads(evidence['receipts/native/composition.json'])
    require(original['runtime_commit'] == RUNTIME and original['apps'] == 26 and original['providers'] == 32,
            'Wrong delivered native composition')
    require(inventory(store) == original['store'], 'Delivered store inventory differs')
    require(len(sd) == 81 and len(full) == 0x1000000 and sha(full) == receipt['full_image']['sha256'],
            'Incomplete delivered SD/full image')
    require(set(components) == set(original['components']), 'Native component set differs')
    for name, entry in original['components'].items():
        raw = components[name]
        require(sha(raw) == entry['sha256'] and len(raw) == entry['bytes'] and
                full[entry['offset']:entry['offset'] + len(raw)] == raw,
                'Delivered native component mismatch: ' + name)
    return receipt, original, store, sd, full, components, evidence


def validate_files(directory, system, old, previous_build, lock):
    require(lock['product_version'] == VERSION and lock['files_version'] == FILES_VERSION and
            lock['system_commit'] == SYSTEM and lock['system_tree'] == SYSTEM_TREE,
            'Files qualification lock has wrong source/version')
    artifacts = {name: (directory / name).read_bytes() for name in FILES_NAMES}
    require(inventory(artifacts) == lock['artifacts'], 'Files artifacts differ from exact qualification lock')
    manifest, previous = json.loads(artifacts['file_browser.json']), json.loads(old['file_browser.json'])
    require(manifest['version'] == FILES_VERSION and previous['version'] == '1.5.28', 'Wrong Files version')
    require({k: v for k, v in manifest.items() if k != 'version'} ==
            {k: v for k, v in previous.items() if k != 'version'}, 'Files manifest authority changed')
    raw = artifacts['file_browser.elf']
    require(raw.startswith(b'\x7fELF') and raw != old['file_browser.elf'], 'Missing changed Files ELF')
    build = json.loads(artifacts['file_browser-build-record.json'])
    require(build['repository_commit'] == SYSTEM and build['working_tree_dirty'] is False and
            build['version'] == FILES_VERSION and build['sha256'] == sha(raw) and build['size_bytes'] == len(raw),
            'Files build receipt mismatch')
    # A version increment cannot silently change the delivered profile or authority.
    for key in ('defines', 'build_defines', 'required_grants', 'requested_capabilities',
                'grant_count', 'grant_bindings', 'profile', 'storage_selection'):
        require(build[key] == previous_build[key], 'Files profile/grants changed: ' + key)
    boot = json.loads(old['boot.json'])
    rows = [r for r in boot['app_capabilities'] if r['manifest'] == 'file_browser.json']
    require(len(rows) == 1 and 'image_source' not in rows[0], 'Files must remain internal-only')
    from compose_shared_settings_090 import resolved_grants
    keys = lambda rows: sorted((r['capability'], r['api'], r['instance_id']) for r in rows)
    require(len(rows[0]['grants']) == build['grant_count'] == 16 and
            keys(resolved_grants(build['required_grants'], rows[0]['grants'])) == keys(rows[0]['grants']),
            'Files must preserve exact 16-grant authority')
    sources = build['source_sha256']
    require('Apps/file_browser.c' in sources and 'Apps/native/file_browser.json' in sources,
            'Missing Files source custody')
    for name, digest in sources.items():
        relative = safe_name(name)
        path = system / str(relative)
        require(path.resolve().is_relative_to(system.resolve()) and
                sha(path.read_bytes()) == digest, 'Files source changed: ' + name)
    require(build['protected_settings']['root'] == '/RTECFG' and
            build['protected_settings']['listing_open_mutation_copy'] is True and
            build['file_sharing']['protected_settings']['direct_recursive_and_peer'] is True,
            'Files protected settings policy differs')
    return artifacts, build


def changed_store(old, artifacts, revision):
    boot = json.loads(old['boot.json'])
    require(len(boot['app_capabilities']) == 26 and len(boot['drivers']) == 32 and
            'shared_settings' not in boot['installation'], 'Delivered authority differs')
    new = dict(old)
    for name in ('file_browser.json', 'file_browser.elf'):
        new[name] = artifacts[name]
    cohort = json.loads(old['cohort.json'])
    require(cohort['version'] == '0.1.90', 'Wrong baseline cohort version')
    cohort.update(version=VERSION, source_revision=revision)
    new['cohort.json'] = encoded(cohort)
    require(new.keys() == old.keys() and {n for n in old if new[n] != old[n]} == ALLOWED,
            'Unexpected internal store changes')
    require(new['boot.json'] == old['boot.json'], 'Boot authority must stay byte-identical')
    return new


def load_assembly_tools(tools, runtime):
    require(__debug__, 'Full image verification requires Python assertions')
    for name, digest in TOOL_HASHES.items():
        require(sha((tools / name).read_bytes()) == digest, 'Assembly tool source differs: ' + name)
    require(sha((runtime / 'scripts/paired_bank_images.py').read_bytes()) == BANK_TOOL_HASH,
            'Bank-state tool source differs')
    sys.path[:0] = [str(tools.resolve() / 'scripts'), str(runtime.resolve() / 'scripts')]
    from current_bootfs import build
    from read_only_spiffs import read_image
    from paired_bank_images import initial_bank_state, parse_record
    return build, read_image, initial_bank_state, parse_record


def verify_image(full, baseline_full, old, expected, components, read_image, parse_record):
    """Decode actual BIN bytes, independently of SPIFFS generation."""
    require(len(full) == len(baseline_full) == 0x1000000, 'Full image must be exactly 16 MiB')
    for start, end in PRESERVED_FLASH:
        require(full[start:end] == baseline_full[start:end], 'Unrelated flash bytes changed')
    require(read_image(baseline_full[slice(*BOOTFS)], 0x510000) == old, 'Baseline full-image store differs')
    require(read_image(full[slice(*BOOTFS)], 0x510000) == expected, 'Final full-image decode differs')
    require(expected.keys() == old.keys() and {n for n in old if expected[n] != old[n]} == ALLOWED,
            'Full image changed unapproved store paths')
    firmware = components['firmware.bin']
    require(('RTE_SOURCE=' + RUNTIME).encode() + b'\0' in firmware, 'Native Runtime marker differs')
    bank = full[slice(*BANK_STATE)]
    pair = parse_record(bank[:96], True)
    require(pair[2] == 0 and pair[3] == len(firmware) and pair[6] == hashlib.sha256(firmware).digest() and
            pair[7] == hashlib.sha256(full[slice(*BOOTFS)]).digest() and bank[96:] == b'\xff' * (8192 - 96),
            'Final bank-state digests/initial state differ')
    return dict(independent_full_image_verified=True, native_unchanged=True,
                boot_authority_unchanged=True, changed_store_paths=sorted(ALLOWED),
                preserved_store_files=len(old) - len(ALLOWED), full_image_bytes=len(full), full_image_sha256=sha(full))


def compose(a):
    require(not a.output.exists(), 'Output must be new')
    for root, commit, label in ((a.system_source, SYSTEM, 'System'), (a.runtime_source, RUNTIME, 'Runtime')):
        require(git(root, 'rev-parse', 'HEAD') == commit and not git(root, 'status', '--porcelain'),
                'Wrong clean committed ' + label + ' source')
    require(git(a.system_source, 'rev-parse', 'HEAD^{tree}') == SYSTEM_TREE, 'Wrong System tree')
    require(re.fullmatch('[0-9a-f]{40}', a.product_revision or '') and
            git(ROOT, 'rev-parse', 'HEAD') == a.product_revision and not git(ROOT, 'status', '--porcelain'),
            'Product revision must identify this clean committed recipe')
    require(subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', PRODUCT_BASE, 'HEAD']).returncode == 0,
            'Product recipe must descend from published .90 base')
    base_receipt, original, old, sd, full, components, evidence = baseline(a.baseline)
    lock_raw = FILES_LOCK.read_bytes()
    lock = json.loads(lock_raw)
    artifacts, build_record = validate_files(a.files, a.system_source, old,
        json.loads(evidence['receipts/composition/file_browser-build.json']), lock)
    new = changed_store(old, artifacts, a.product_revision)
    firmware = components['firmware.bin']
    require(json.loads(new['cohort.json'])['firmware_sha256'] == sha(firmware) ==
            base_receipt['sources']['firmware_sha256'], 'Native firmware identity changed')
    build, read_image, initial_bank_state, parse_record = load_assembly_tools(a.tools, a.runtime_source)
    image, packing = build(new)
    state = initial_bank_state(firmware, image, True)
    result = bytearray(full)
    result[slice(*BOOTFS)] = image
    result[slice(*BANK_STATE)] = state
    verification = verify_image(bytes(result), full, old, new, components, read_image, parse_record)
    from compose_shared_settings_090 import audit_selected_images
    with tempfile.TemporaryDirectory(prefix='x4-files-092-sd-audit-') as tmp:
        root = Path(tmp)
        write_files(root / 'store', new)
        write_files(root / 'SD', sd)
        selected = audit_selected_images(json.loads(new['boot.json']), root / 'store', root / 'SD')
    old_selected = json.loads(evidence['receipts/composition/shared-settings-composition.json'])['selected_sd_images']
    require(selected == old_selected and len(selected) == 46, 'Selected SD image inventory changed')
    components = dict(components, **{'bootfs.bin': image, 'bank_state.bin': state})
    receipt = dict(product='X4', product_version=VERSION, runtime_commit=RUNTIME,
        system_commit=SYSTEM, system_tree=SYSTEM_TREE, product_source=a.product_revision,
        product_source_dirty=False, product_base=PRODUCT_BASE,
        recipe_sha256=sha(Path(__file__).read_bytes()), files_lock_sha256=sha(lock_raw),
        native_platform_commit=base_receipt['sources']['native_platform_commit'],
        assembly_tools=TOOL_HASHES, bank_state_tool_sha256=BANK_TOOL_HASH,
        baseline_full_image_sha256=sha(full), firmware_sha256=sha(firmware), native_rebuilt=False,
        shared_settings_enabled=False, full_initial_image_erases_internal_data=True,
        sd_overlay_required=False, sd_deliverable_created=False,
        apps=26, providers=32, original_sd_files_preserved=81, added_sd_files=[],
        sd=inventory(sd), selected_sd_images=selected, store=inventory(new),
        files_client=dict(version=FILES_VERSION, system_commit=SYSTEM, artifacts=inventory(artifacts),
                          source_file_count=len(build_record['source_sha256']), grants=16),
        components={n: dict(bytes=len(raw), sha256=sha(raw), offset=original['components'][n]['offset'])
                    for n, raw in components.items()},
        hardware_tested=False, provider_execution_qualified=False,
        persistence_status='unchanged: full flashing erases native-only settings and saved networks', **verification)
    a.output.mkdir(parents=True)
    write_files(a.output / 'store', new)
    write_files(a.output / 'components', components)
    write_files(a.output / 'receipts/files-client', artifacts)
    write_files(a.output / 'receipts', {'files-composition.json': encoded(receipt), 'packing.json': encoded(packing),
        'baseline-native-admission.json': evidence['receipts/admission.json'],
        'baseline-native-composition.json': evidence['receipts/native/composition.json']})
    target = a.output / IMAGE_NAME
    target.write_bytes(result)
    require(target.read_bytes() == result, 'Written full image differs')
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'files', 'system-source', 'runtime-source', 'tools', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--product-revision', required=True)
    a = p.parse_args()
    print(json.dumps(compose(a), indent=2))


if __name__ == '__main__':
    main()
