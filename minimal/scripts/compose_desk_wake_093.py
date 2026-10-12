#!/usr/bin/env python3
"""Compose Home-only X4 .93 from the exact delivered .92 full image.

No native build, device access, network, publication, or SD deliverable. The full
initial image erases internal data. --self-test exercises packing and negative
custody checks with synthetic Home bytes; it does not qualify target execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BASE_RECEIPT_SHA = '4690a1b4942bdebf0dcce7aa9362afe0b940453015ba792fc8def68ffc233365'
BASE_FULL_SHA = 'dd9196dfdf8fc6a65b0f1e675d21fbf83df31b752316c5906dcb5be7fea8bc30'
PRODUCT_BASE = '5b32e39f5f538c27a72d515021e17cb4c0355111'
RUNTIME = '3b90cd11cf0ff4e8116bb54d2d9eb9c7c67a148b'
SYSTEM = '1aaf53e23ca9651a5cf9d1debe44941c9d7d0e58'
SYSTEM_TREE = 'df34bc79caeee0815230d2a35ec1995606ec66d6'
VERSION, HOME_VERSION = '0.1.93', '0.4.12'
IMAGE_NAME = 'X4-0.1.93-FULL-INITIAL-ERASES-DATA.bin'
BASE_IMAGE_NAME = 'X4-0.1.92-FULL-INITIAL-ERASES-DATA.bin'
HOME_NAMES = ('default.elf', 'default.json', 'build-evidence.json')
ALLOWED = {'default.elf', 'default.json', 'cohort.json'}
HELPERS = {
    'compose_files_092.py': '9bdb6849cefb213175c72827307bd11af479eb7e001f2b893d0875cb06f997f6',
    'compose_shared_settings_090.py': '673703f7a8432dbba4335c407eb6e43afff480d0f7b6e22bf7678654165d4af4',
}


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


def read_tree(root):
    require(root.is_dir() and not root.is_symlink(), 'Missing/unsafe input directory: ' + str(root))
    files = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Symlinked input: ' + str(path))
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_bytes()
        else:
            require(path.is_dir(), 'Nonregular input: ' + str(path))
    return files


def helpers():
    for name, digest in HELPERS.items():
        require(sha((Path(__file__).parent / name).read_bytes()) == digest,
                'Composition helper source differs: ' + name)
    from compose_files_092 import load_assembly_tools, write_files, BOOTFS, BANK_STATE, PRESERVED_FLASH
    from compose_shared_settings_090 import audit_selected_images
    return load_assembly_tools, write_files, BOOTFS, BANK_STATE, PRESERVED_FLASH, audit_selected_images


def baseline(folder, sd_root):
    receipt_raw = (folder / 'receipts/files-composition.json').read_bytes()
    require(sha(receipt_raw) == BASE_RECEIPT_SHA, 'Not the exact qualified .92 receipt')
    receipt = json.loads(receipt_raw)
    require(receipt['product_version'] == '0.1.92' and receipt['runtime_commit'] == RUNTIME and
            receipt['files_client']['version'] == '1.5.30', 'Wrong baseline product/Files/Runtime')
    store, components, sd = read_tree(folder / 'store'), read_tree(folder / 'components'), read_tree(sd_root)
    full = (folder / BASE_IMAGE_NAME).read_bytes()
    require(len(full) == 0x1000000 and sha(full) == BASE_FULL_SHA == receipt['full_image_sha256'],
            'Not the exact delivered .92 full image')
    require(inventory(store) == receipt['store'], 'Baseline store inventory differs')
    require(inventory(sd) == receipt['sd'] and len(sd) == 81, 'Baseline SD inventory differs')
    require(set(components) == set(receipt['components']), 'Baseline component inventory differs')
    for name, entry in receipt['components'].items():
        raw = components[name]
        require(sha(raw) == entry['sha256'] and len(raw) == entry['bytes'] and
                full[entry['offset']:entry['offset'] + len(raw)] == raw,
                'Baseline component/full-image mismatch: ' + name)
    require(json.loads(store['file_browser.json'])['version'] == '1.5.30', 'Files 1.5.30 missing')
    return receipt, receipt_raw, store, sd, full, components


def validate_payload(artifacts, old, lock):
    require(lock.get('product_version') == VERSION and lock.get('home_version') == HOME_VERSION and
            lock.get('system_commit') == SYSTEM and lock.get('system_tree') == SYSTEM_TREE,
            'Home qualification lock has wrong source/version')
    require(set(artifacts) == set(HOME_NAMES) and inventory(artifacts) == lock.get('artifacts'),
            'Home artifacts differ from exact qualification lock')
    manifest, previous = json.loads(artifacts['default.json']), json.loads(old['default.json'])
    require(previous['version'] == '0.4.11' and manifest == dict(previous, version=HOME_VERSION),
            'Home manifest authority/identity changed')
    raw = artifacts['default.elf']
    require(raw.startswith(b'\x7fELF') and raw != old['default.elf'], 'Missing changed Home ELF')
    evidence = json.loads(artifacts['build-evidence.json'])
    require(evidence.get('repository_commit') == SYSTEM and evidence.get('working_tree_dirty') is False and
            evidence.get('version') == HOME_VERSION and evidence.get('upstream_profile_version') == '0.4.11' and
            evidence.get('sha256') == sha(raw) and evidence.get('size_bytes') == len(raw),
            'Home build evidence source/version/artifact mismatch')
    require(evidence.get('desk_clock') is True and evidence.get('sparse_start') is True and
            evidence.get('provider_activation') == 'demand' and evidence.get('timer_preferences') == 'retained-only' and
            evidence.get('grant_count') == 19 and evidence.get('grant_bindings') == {'storage.app-data': [62]},
            'Home retained clock profile/grants changed')
    boot = json.loads(old['boot.json'])
    rows = [r for r in boot['app_capabilities'] if r['manifest'] == 'default.json']
    require(len(rows) == 1 and 'image_source' not in rows[0] and len(rows[0]['grants']) == 22,
            'Home must preserve delivered internal-only boot authority')
    return evidence


def clean_source(root, commit, label):
    require(re.fullmatch('[0-9a-f]{40}', commit or '') and git(root, 'rev-parse', 'HEAD') == commit and
            not git(root, 'status', '--porcelain', '--untracked-files=all'),
            label + ' must be exact clean committed source')


def validate_sources(a, lock, evidence):
    clean_source(a.runtime_source, RUNTIME, 'Runtime')
    clean_source(a.system_source, SYSTEM, 'System')
    require(git(a.system_source, 'rev-parse', 'HEAD^{tree}') == SYSTEM_TREE, 'Wrong System tree')
    clean_source(ROOT, a.product_revision, 'Product recipe')
    product = evidence.get('x4_product', {})
    source = lock.get('product_commit')
    require(re.fullmatch('[0-9a-f]{40}', source or '') and product.get('commit') == source and
            product.get('dirty') is False, 'Home product build source missing/dirty')
    require(product.get('base') == PRODUCT_BASE and product.get('version') == VERSION and
            product.get('timer_storage_transaction') == {'capability': 'storage.volume', 'instance': 9,
                'prepare_commit': True, 'checked_resume': True} and
            product.get('recipe_sha256') == sha((ROOT / 'minimal/scripts/build_desk_wake_093.py').read_bytes()),
            'Home product build recipe/transaction differs')
    for earlier, later in ((PRODUCT_BASE, source), (source, a.product_revision)):
        require(subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', earlier, later],
                               stdout=subprocess.DEVNULL).returncode == 0,
                'Product target/recipe must descend from published .92')
    changed = git(ROOT, 'diff', '--name-only', source, a.product_revision).splitlines()
    approved = {'minimal/scripts/compose_desk_wake_093.py', 'minimal/desk-wake-093-inputs.json',
                'minimal/docs/DESK_WAKE_093.md'}
    require(all(n in approved or n.startswith('minimal/docs/evidence/desk-wake-093/') for n in changed),
            'Product changed beyond packaging recipe/evidence since target build')
    require(evidence.get('local_sleep_source_sha256') == sha((ROOT / 'minimal/apps/portable_sleep.c').read_bytes()),
            'Home local sleep source differs from committed product')
    sources = evidence.get('desk_sources', {})
    require('Apps/paper_clock.c' in sources and 'Apps/paper_sparse_clock.inc' in sources,
            'Home desk source custody missing')
    for name, digest in sources.items():
        path = a.system_source / name
        require(not path.is_symlink() and path.resolve().is_relative_to(a.system_source.resolve()) and
                sha(path.read_bytes()) == digest, 'Home System source changed: ' + name)
    return source, changed


def changed_store(old, artifacts, revision):
    boot = json.loads(old['boot.json'])
    require(len(boot['app_capabilities']) == 26 and len(boot['drivers']) == 32 and
            'shared_settings' not in boot['installation'], 'Delivered boot authority differs')
    new = dict(old)
    new.update({n: artifacts[n] for n in ('default.elf', 'default.json')})
    cohort = json.loads(old['cohort.json'])
    require(cohort['version'] == '0.1.92', 'Wrong baseline cohort')
    new['cohort.json'] = encoded(dict(cohort, version=VERSION, source_revision=revision))
    require(new.keys() == old.keys() and {n for n in old if old[n] != new[n]} == ALLOWED,
            'Unexpected internal store changes')
    return new


def verify_image(full, base_full, old, new, components, read_image, parse_record):
    _, _, bootfs, bank_state, preserved, _ = helpers()
    require(len(full) == len(base_full) == 0x1000000, 'Full image must be exactly 16 MiB')
    for start, end in preserved:
        require(full[start:end] == base_full[start:end], 'Unrelated flash bytes changed')
    require(read_image(base_full[slice(*bootfs)], 0x510000) == old, 'Baseline full-image store differs')
    require(read_image(full[slice(*bootfs)], 0x510000) == new, 'Final full-image store differs')
    require(new.keys() == old.keys() and {n for n in old if new[n] != old[n]} == ALLOWED,
            'Unapproved store mutation')
    require(new['boot.json'] == old['boot.json'] and new['file_browser.elf'] == old['file_browser.elf'] and
            new['file_browser.json'] == old['file_browser.json'], 'Files/boot authority changed')
    firmware = components['firmware.bin']
    require(('RTE_SOURCE=' + RUNTIME).encode() + b'\0' in firmware, 'Native Runtime marker differs')
    cohort = json.loads(new['cohort.json'])
    require(cohort['firmware_sha256'] == sha(firmware) and cohort['firmware_size'] == len(firmware),
            'Cohort native identity differs')
    state = full[slice(*bank_state)]
    record = parse_record(state[:96], True)
    require(record[2] == 0 and record[3] == len(firmware) and record[6] == hashlib.sha256(firmware).digest() and
            record[7] == hashlib.sha256(full[slice(*bootfs)]).digest() and
            state[96:] == b'\xff' * (8192 - 96), 'Final bank-state digests/initial state differ')
    return dict(independent_full_image_verified=True, native_unchanged=True, boot_authority_unchanged=True,
                files_1_5_30_unchanged=True, changed_store_paths=sorted(ALLOWED),
                preserved_store_files=len(old) - len(ALLOWED), preserved_flash_ranges=[list(x) for x in preserved],
                full_image_bytes=len(full), full_image_sha256=sha(full))


def compose(a):
    require(not a.output.exists(), 'Output must be new')
    load_tools, write_files, bootfs, bank_state, _, audit_sd = helpers()
    base, base_raw, old, sd, full, components = baseline(a.baseline, a.sd)
    lock_raw = a.home_lock.read_bytes()
    lock = json.loads(lock_raw)
    artifacts = {n: (a.home / n).read_bytes() for n in HOME_NAMES}
    evidence = validate_payload(artifacts, old, lock)
    source, packaging_changes = validate_sources(a, lock, evidence)
    new = changed_store(old, artifacts, a.product_revision)
    build, read_image, initial_bank_state, parse_record = load_tools(a.tools, a.runtime_source)
    image, packing = build(new)
    state = initial_bank_state(components['firmware.bin'], image, True)
    result = bytearray(full)
    result[slice(*bootfs)], result[slice(*bank_state)] = image, state
    proof = verify_image(bytes(result), full, old, new, components, read_image, parse_record)
    with tempfile.TemporaryDirectory(prefix='x4-desk-093-sd-audit-') as tmp:
        root = Path(tmp)
        write_files(root, new)
        selected = audit_sd(json.loads(new['boot.json']), root, a.sd)
    require(selected == base['selected_sd_images'] and len(selected) == 46, 'Selected SD inventory changed')
    components = dict(components, **{'bootfs.bin': image, 'bank_state.bin': state})
    receipt = dict(product='X4', product_version=VERSION, product_source=a.product_revision,
        product_source_dirty=False, product_base=PRODUCT_BASE, product_tree=git(ROOT, 'rev-parse', 'HEAD^{tree}'),
        home_product_source=source, packaging_only_changes=packaging_changes,
        system_commit=SYSTEM, system_tree=SYSTEM_TREE, runtime_commit=RUNTIME,
        recipe_sha256=sha(Path(__file__).read_bytes()), helper_sha256=HELPERS,
        home_lock_sha256=sha(lock_raw), baseline_receipt_sha256=sha(base_raw), baseline_full_image_sha256=sha(full),
        native_platform_commit=base['native_platform_commit'], firmware_sha256=sha(components['firmware.bin']),
        native_rebuilt=False, assembly_tools=base['assembly_tools'], bank_state_tool_sha256=base['bank_state_tool_sha256'],
        apps=26, providers=32, store=inventory(new), sd=inventory(sd), selected_sd_images=selected,
        original_sd_files_preserved=81, sd_inventory_verified=True, added_sd_files=[],
        sd_overlay_required=False, sd_deliverable_created=False, shared_settings_enabled=False,
        home_client=dict(version=HOME_VERSION, upstream_profile_version='0.4.11', artifacts=inventory(artifacts),
                         product_commit=source, system_commit=SYSTEM, required_capabilities=19, boot_grants=22),
        files_client=base['files_client'], full_initial_image_erases_internal_data=True,
        components={n: dict(bytes=len(raw), sha256=sha(raw), offset=base['components'][n]['offset'])
                    for n, raw in components.items()},
        hardware_tested=False, provider_execution_qualified=False,
        persistence_status=base['persistence_status'], **proof)
    a.output.mkdir(parents=True)
    write_files(a.output / 'store', new)
    write_files(a.output / 'components', components)
    write_files(a.output / 'receipts/home-client', artifacts)
    write_files(a.output / 'receipts/baseline', read_tree(a.baseline / 'receipts'))
    write_files(a.output / 'receipts', {'desk-wake-composition.json': encoded(receipt),
        'home-qualification-lock.json': lock_raw, 'packing.json': encoded(packing)})
    target = a.output / IMAGE_NAME
    target.write_bytes(result)
    require(target.read_bytes() == result and inventory(read_tree(a.output / 'store')) == receipt['store'] and
            inventory(read_tree(a.output / 'components')) == inventory(components), 'Written output differs')
    return receipt


def self_test(a):
    """Real baseline and image round trip; synthetic Home must never be delivered."""
    load_tools, _, bootfs, bank_state, _, audit_sd = helpers()
    base, _, old, sd, full, components = baseline(a.baseline, a.sd)
    require(audit_sd(json.loads(old['boot.json']), a.baseline / 'store', a.sd) == base['selected_sd_images'],
            'Baseline SD selection differs')
    manifest = dict(json.loads(old['default.json']), version=HOME_VERSION)
    raw = old['default.elf'] + b'\0COMPOSER-SELF-TEST-NOT-A-TARGET\0'
    evidence = dict(version=HOME_VERSION, upstream_profile_version='0.4.11', repository_commit=SYSTEM,
        working_tree_dirty=False, sha256=sha(raw), size_bytes=len(raw), desk_clock=True, sparse_start=True,
        provider_activation='demand', timer_preferences='retained-only', grant_count=19,
        grant_bindings={'storage.app-data': [62]})
    artifacts = {'default.elf': raw, 'default.json': encoded(manifest), 'build-evidence.json': encoded(evidence)}
    lock = dict(product_version=VERSION, home_version=HOME_VERSION, system_commit=SYSTEM,
                system_tree=SYSTEM_TREE, artifacts=inventory(artifacts))
    validate_payload(artifacts, old, lock)
    count = 0
    def rejects(fn):
        nonlocal count
        try:
            fn()
        except (ValueError, AssertionError):
            count += 1
        else:
            raise AssertionError('Expected negative custody check to fail')
    rejects(lambda: validate_payload(dict(artifacts, **{'default.elf': raw + b'x'}), old, lock))
    bad = dict(artifacts, **{'default.json': encoded(dict(manifest, requires=[]))})
    rejects(lambda: validate_payload(bad, old, dict(lock, artifacts=inventory(bad))))
    bad = dict(artifacts, **{'build-evidence.json': encoded(dict(evidence, working_tree_dirty=True))})
    rejects(lambda: validate_payload(bad, old, dict(lock, artifacts=inventory(bad))))
    rejects(lambda: validate_payload(artifacts, old, dict(lock, system_commit='0' * 40)))
    new = changed_store(old, artifacts, '1' * 40)
    build, read_image, initial_bank_state, parse_record = load_tools(a.tools, a.runtime_source)
    image, packing = build(new)
    result = bytearray(full)
    result[slice(*bootfs)] = image
    result[slice(*bank_state)] = initial_bank_state(components['firmware.bin'], image, True)
    proof = verify_image(bytes(result), full, old, new, components, read_image, parse_record)
    bad = bytearray(result); bad[0x10000] ^= 1
    rejects(lambda: verify_image(bytes(bad), full, old, new, components, read_image, parse_record))
    bad = bytearray(result); bad[bank_state[0] + 40] ^= 1
    rejects(lambda: verify_image(bytes(bad), full, old, new, components, read_image, parse_record))
    bad = dict(new, **{'file_browser.elf': new['file_browser.elf'] + b'x'})
    rejects(lambda: verify_image(bytes(result), full, old, bad, components, read_image, parse_record))
    with tempfile.TemporaryDirectory(prefix='x4-desk-093-negative-') as tmp:
        root = Path(tmp); (root / 'escape').symlink_to(a.baseline / 'store/default.elf')
        rejects(lambda: read_tree(root))
    return dict(self_test='PASS', target_execution_tested=False, synthetic_output_written=False,
                negative_checks=count, baseline_sd_files=len(sd), independent_round_trip=proof,
                packing=packing)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'runtime-source', 'tools', 'sd'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('home', 'home-lock', 'system-source', 'output'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--product-revision')
    p.add_argument('--self-test', action='store_true')
    a = p.parse_args()
    if not a.self_test:
        for name in ('home', 'home_lock', 'system_source', 'output', 'product_revision'):
            if getattr(a, name) is None:
                p.error('--' + name.replace('_', '-') + ' is required for composition')
    print(json.dumps(self_test(a) if a.self_test else compose(a), indent=2))


if __name__ == '__main__':
    main()
