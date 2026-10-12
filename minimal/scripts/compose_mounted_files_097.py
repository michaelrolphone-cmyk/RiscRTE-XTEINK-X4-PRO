#!/usr/bin/env python3
"""Local .97 Files preflight over delivered .96; publication/rebuild still required.

This recipe intentionally cannot create a release deliverable. It writes a
clearly labelled local test image for complete-image admission. No network,
device, publication or Library operation is performed.
"""
import argparse
import copy
import json
import tempfile
import zipfile
from pathlib import Path

from compose_desk_wake_093 import clean_source, read_tree
from compose_files_092 import (BANK_STATE, BOOTFS, encoded, git, inventory,
    load_assembly_tools, require, safe_name, sha, write_files)
from compose_shared_settings_090 import audit_selected_images, resolved_grants
from compose_sd_lifecycle_096 import verify_image
from boot_order_spiffs import build as ordered_build, ordered_paths
from sd_resident_lifecycle import validate as validate_lifecycle

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / 'minimal/files-mounted-097-inputs.json'
VERSION = '0.1.97'
BASE = '075f7a70d186fcbc5e93e0a8c10b4a16bd23d02c'
IMAGE = 'X4-0.1.97-LOCAL-PREFLIGHT-NOT-FOR-DELIVERY.bin'
ALLOWED = {'cohort.json', 'file_browser.json', 'file_browser.elf'}
FILES_NAMES = ('file_browser.json', 'file_browser.elf', 'file_browser-build-record.json')


def load_lock():
    lock = json.loads(LOCK_PATH.read_bytes())
    require(lock['product_version'] == VERSION and lock['product_base'] == BASE and
            lock['local_preflight_only'] is True and lock['published_system_commit'] is None and
            lock['publication_blocked'] is True and
            lock['rebuild_from_final_published_system_required'] is True,
            'This recipe is local preflight only; final source pins and rebuild are pending')
    return lock


def baseline(folder, lock):
    for name, digest in lock['baseline_receipts'].items():
        require(sha((folder / name).read_bytes()) == digest, 'Baseline receipt changed: ' + name)
    receipt = json.loads((folder / 'receipts/sd-lifecycle-composition.json').read_bytes())
    require(receipt['product_version'] == '0.1.96' and receipt['product_source'] == BASE and
            receipt['runtime_commit'] == lock['runtime_commit'] and
            receipt['runtime_tree'] == lock['runtime_tree'], 'Wrong delivered .96 source')
    full = (folder / 'X4-0.1.96-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
    require(len(full) == 0x1000000 and
            sha(full) == receipt['full_image_sha256'] == lock['baseline_full_image_sha256'],
            'Baseline full image changed')
    old, sd, parts = (read_tree(folder / name) for name in ('store', 'SD', 'components'))
    require(inventory(old) == receipt['store'] and len(old) == 103, 'Baseline store changed')
    require(inventory(sd) == receipt['sd'] and len(sd) == 81, 'Baseline SD changed')
    require(set(parts) == set(receipt['components']), 'Baseline component set changed')
    for name, row in receipt['components'].items():
        part = parts[name]
        require(len(part) == row['bytes'] and sha(part) == row['sha256'] and
                full[row['offset']:row['offset'] + len(part)] == part,
                'Baseline component/image mismatch: ' + name)
    require(sha(parts['firmware.bin']) == lock['native_firmware_sha256'] and
            receipt['firmware_elf_sha256'] == lock['native_elf_sha256'], 'Native identity changed')
    overlay = folder / lock['baseline_overlay']['name']
    require(sha(overlay.read_bytes()) == lock['baseline_overlay']['sha256'] and
            overlay.stat().st_size == lock['baseline_overlay']['bytes'], 'Delivered .96 overlay changed')
    with zipfile.ZipFile(overlay) as z:
        require(len(z.namelist()) == len(set(z.namelist())), 'Duplicate baseline overlay path')
        files = {n: z.read(n) for n in z.namelist()}
        require(inventory(files) == lock['baseline_overlay']['files'] and
                all(sd[n] == data for n, data in files.items()), 'SD tree does not include .96 overlay')
    require(validate_lifecycle(old, sd) == receipt['sd_lifecycle'], 'Baseline lifecycle mismatch')
    return receipt, old, sd, parts, full


def validate_files(artifacts, system, old, lock):
    require(set(artifacts) == set(FILES_NAMES) and inventory(artifacts) == lock['files_artifacts'],
            'Files preflight artifacts differ from lock')
    manifest, previous = json.loads(artifacts['file_browser.json']), json.loads(old['file_browser.json'])
    require(previous['version'] == '1.5.30' and
            manifest == dict(previous, version=lock['files_version']), 'Files manifest authority changed')
    raw, record = artifacts['file_browser.elf'], json.loads(artifacts['file_browser-build-record.json'])
    require(raw.startswith(b'\x7fELF') and raw != old['file_browser.elf'] and
            record['repository_commit'] == lock['system_build_commit'] and
            record['working_tree_dirty'] is False and record['version'] == lock['files_version'] and
            record['sha256'] == sha(raw) and record['size_bytes'] == len(raw), 'Files source/build mismatch')
    for key, expected in lock['profile_invariants'].items():
        require(record[key] == expected, 'Files profile/authority changed: ' + key)
    boot = json.loads(old['boot.json'])
    rows = [r for r in boot['app_capabilities'] if r['manifest'] == 'file_browser.json']
    require(len(rows) == 1 and 'image_source' not in rows[0], 'Files must remain internal')
    keys = lambda grants: sorted((r['capability'], r['api'], r['instance_id']) for r in grants)
    require(len(rows[0]['grants']) == record['grant_count'] == 16 and
            keys(resolved_grants(record['required_grants'], rows[0]['grants'])) == keys(rows[0]['grants']),
            'Files must preserve exact 16-grant authority')
    require(len(record['source_sha256']) == lock['source_hash_count'] == 312,
            'Files source inventory incomplete')
    for name, digest in record['source_sha256'].items():
        safe_name(name)
        path = system / name
        require(path.resolve().is_relative_to(system.resolve()) and sha(path.read_bytes()) == digest,
                'Compiled source changed: ' + name)
        committed = __import__('subprocess').check_output(
            ['git', '-C', str(system), 'show', lock['system_build_commit'] + ':' + name])
        require(sha(committed) == digest, 'Build source commit mismatch: ' + name)
    require(record['protected_settings']['root'] == '/RTECFG' and
            record['protected_settings']['listing_open_mutation_copy'] is True and
            record['file_sharing']['protected_settings']['direct_recursive_and_peer'] is True,
            'Protected settings policy changed')
    return record


def payload(old, sd, artifacts, revision, lifecycle):
    new = dict(old)
    new.update({name: artifacts[name] for name in ('file_browser.elf', 'file_browser.json')})
    cohort = json.loads(old['cohort.json'])
    require(cohort['version'] == '0.1.96' and cohort['source_revision'] == BASE,
            'Baseline cohort identity mismatch')
    cohort.update(version=VERSION, source_revision=revision)
    new['cohort.json'] = encoded(cohort)
    verify_payload(old, new, sd, sd, artifacts, revision, lifecycle)
    return new


def verify_payload(old, new, old_sd, sd, artifacts, revision, lifecycle):
    require(old.keys() == new.keys() and {n for n in old if old[n] != new[n]} == ALLOWED,
            'Unexpected internal changes')
    require(old_sd == sd, 'Any SD change is forbidden relative to delivered .96')
    expected = json.loads(old['cohort.json'])
    expected.update(version=VERSION, source_revision=revision)
    require(new['cohort.json'] == encoded(expected), 'Unexpected cohort changes')
    for name in ('file_browser.elf', 'file_browser.json'):
        require(new[name] == artifacts[name], 'Unbound Files artifact: ' + name)
    require(ordered_paths(old) == ordered_paths(new), 'Boot packing order changed')
    require(validate_lifecycle(new, sd) == lifecycle, 'SD resident lifecycle changed')


def compose(a):
    require(a.preflight_only, 'Only --preflight-only is supported while publication is pending')
    require(not a.output.exists(), 'Output must be new')
    lock = load_lock()
    clean_source(ROOT, a.product_revision, 'Product')
    require(git(ROOT, 'merge-base', BASE, a.product_revision) == BASE, 'Product must descend from .96')
    clean_source(a.runtime_source, lock['runtime_commit'], 'Runtime')
    require(git(a.runtime_source, 'rev-parse', 'HEAD^{tree}') == lock['runtime_tree'], 'Wrong Runtime tree')
    clean_source(a.system_source, lock['system_qualification_commit'], 'System qualification')
    require(git(a.system_source, 'rev-parse', 'HEAD^{tree}') == lock['system_qualification_tree'] and
            git(a.system_source, 'rev-parse', lock['system_build_commit'] + '^{tree}') == lock['system_build_tree'],
            'Wrong local System source trees')
    base, old, sd, parts, full = baseline(a.baseline, lock)
    artifacts = {n: (a.files / n).read_bytes() for n in FILES_NAMES}
    record = validate_files(artifacts, a.system_source, old, lock)
    new = payload(old, sd, artifacts, a.product_revision, base['sd_lifecycle'])
    build, read_image, initial, parse = load_assembly_tools(a.tools, a.runtime_source)
    image, packing = ordered_build(new, build)
    state = initial(parts['firmware.bin'], image, True)
    result = bytearray(full)
    result[slice(*BOOTFS)], result[slice(*BANK_STATE)] = image, state
    verify_image(bytes(result), full, old, new, read_image, parse, parts['firmware.bin'])
    with tempfile.TemporaryDirectory(prefix='x4-097-selected-') as tmp:
        root = Path(tmp)
        write_files(root / 'store', new)
        write_files(root / 'SD', sd)
        selected = audit_selected_images(json.loads(new['boot.json']), root / 'store', root / 'SD')
    require(selected == base['selected_sd_images'] and len(selected) == 46, 'Selected SD executables changed')
    parts = dict(parts, **{'bootfs.bin': image, 'bank_state.bin': state})
    receipt = copy.deepcopy(base)
    receipt.pop('files_1_5_30_unchanged', None)
    receipt.pop('sd_overlay', None)
    receipt.update(product_version=VERSION, product_source=a.product_revision,
        product_tree=git(ROOT, 'rev-parse', 'HEAD^{tree}'), product_base=BASE,
        baseline_full_image_sha256=lock['baseline_full_image_sha256'],
        baseline_receipt_sha256=lock['baseline_receipts']['receipts/sd-lifecycle-composition.json'],
        baseline_receipts=lock['baseline_receipts'], local_preflight_only=True,
        publication_ready=False, final_published_system_source_pending=True,
        final_rebuild_required=True, product_published=False, system_published=False,
        system_commit=lock['system_build_commit'], system_tree=lock['system_build_tree'],
        system_qualification_commit=lock['system_qualification_commit'],
        native_rebuilt=False, native_unchanged=True, home_rebuilt=False,
        packaging_only_changes=False, files_replaced=True,
        files_client=dict(version=lock['files_version'], system_commit=lock['system_build_commit'],
                          artifacts=inventory(artifacts), grants=16, source_file_count=312),
        recipe_sha256=sha(Path(__file__).read_bytes()), files_lock_sha256=sha(LOCK_PATH.read_bytes()),
        store=inventory(new), sd=inventory(sd), packing_sha256=sha(encoded(packing)),
        changed_store_paths=sorted(ALLOWED), changed_sd_paths=[],
        sd_overlay_required=False, sd_deliverable_created=False,
        sd_baseline_requires_delivered_096_overlay=True, baseline_sd_overlay=lock['baseline_overlay'],
        original_sd_files_preserved=81, all_sd_executables_preserved=True, preserved_store_files=100,
        components={n: dict(bytes=len(v), sha256=sha(v), offset=base['components'][n]['offset']) for n,v in parts.items()},
        full_image_bytes=len(result), full_image_sha256=sha(result), hardware_tested=False)
    a.output.mkdir(parents=True)
    write_files(a.output / 'store', new)
    write_files(a.output / 'SD', sd)
    write_files(a.output / 'components', parts)
    write_files(a.output / 'receipts/files-client', artifacts)
    write_files(a.output / 'receipts', {'mounted-files-composition.json': encoded(receipt),
        'packing.json': encoded(packing), 'baseline-sd-lifecycle-composition.json': encoded(base)})
    (a.output / IMAGE).write_bytes(result)
    require((a.output / IMAGE).read_bytes() == result, 'Written image mismatch')
    require(read_tree(a.output / 'store') == new and read_tree(a.output / 'SD') == sd,
            'Written store/SD mismatch')
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'files', 'system-source', 'runtime-source', 'tools', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--product-revision', required=True)
    p.add_argument('--preflight-only', action='store_true')
    print(json.dumps(compose(p.parse_args()), indent=2))


if __name__ == '__main__':
    main()
