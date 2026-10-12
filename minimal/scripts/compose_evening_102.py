#!/usr/bin/env python3
"""Compose RF and first-attempt alarm fixes over the exact delivered X4 .101.

No native rebuild, flash operation, SD data removal, or experimental settings
binding is performed. Reuse qualified component builds with pinned source trees.
"""
import argparse
import copy
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from compose_desk_wake_093 import read_tree, clean_source
from compose_files_092 import (require, sha, encoded, inventory, git, write_files,
    load_assembly_tools, BOOTFS, BANK_STATE)
from compose_keyboard_100 import verify_image
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / 'minimal/evening-102-inputs.json'
VERSION = '0.1.102'
IMAGE = 'X4-0.1.102-FULL-INITIAL-ERASES-DATA.bin'
ZIP = 'X4-0.1.102-Combined-Changed-SD.zip'
CHANGED = {'boot.json', 'cohort.json', 'waterfall.json', 'default.elf',
           'default.json', 'alarm/driver.elf', 'alarm/manifest.json'}
SD_CHANGED = {'Apps/waterfall/waterfall.elf', 'Apps/waterfall/manifest.json'}


def checked_files(root, expected):
    result = {}
    for name, row in expected.items():
        data = (root / name).read_bytes()
        require(sha(data) == row['sha256'] and len(data) == row['bytes'],
                'Component custody mismatch: ' + name)
        result[name] = data
    return result


def payload(old, old_sd, rf, rtc, revision):
    new, sd = dict(old), dict(old_sd)
    for name, version in [('waterfall.json', '0.3.3'), ('default.json', '0.4.14'),
                           ('alarm/manifest.json', '0.4.10')]:
        data = rf[name] if name == 'waterfall.json' else rtc['x4/store/' + name]
        require(json.loads(data) == dict(json.loads(old[name]), version=version),
                'Manifest authority changed: ' + name)
        new[name] = data
    for name in ['default.elf', 'alarm/driver.elf']:
        new[name] = rtc['x4/store/' + name]
    sd['Apps/waterfall/waterfall.elf'] = rf['waterfall.elf']
    sd['Apps/waterfall/manifest.json'] = new['waterfall.json']
    boot = json.loads(old['boot.json'])
    require('shared_settings' not in boot.get('installation', {}),
            'Unqualified shared settings binding')
    original_boot = copy.deepcopy(boot)
    row = next(r for r in boot['drivers'] if r['manifest'] == 'alarm/manifest.json')
    source = row['image_source']
    require(source['internal_fallback'] is True and source['volume_instance'] == 9,
            'Unexpected alarm fallback authority')
    previous = source['path']
    require(old_sd[previous] == old['alarm/driver.elf'], 'Stale baseline SD alarm')
    current = str(PurePosixPath(previous).parent / ('image-' + sha(new['alarm/driver.elf']) + '.elf'))
    require(current not in old_sd, 'Immutable alarm image collision')
    source['path'] = current
    sd[current] = new['alarm/driver.elf']
    restored = copy.deepcopy(boot)
    next(r for r in restored['drivers'] if r['manifest'] == 'alarm/manifest.json')['image_source']['path'] = previous
    require(restored == original_boot, 'Boot grant or selection authority changed')
    new['boot.json'] = encoded(boot)
    cohort = json.loads(old['cohort.json'])
    require(cohort['version'] == '0.1.101' and cohort['runtime_version'] == '0.2.28',
            'Wrong predecessor cohort')
    cohort.update(version=VERSION, source_revision=revision)
    new['cohort.json'] = encoded(cohort)
    require(set(new) == set(old) and {n for n in old if new[n] != old[n]} == CHANGED,
            'Unrelated store changes')
    require(set(old_sd) <= set(sd) and set(sd) - set(old_sd) == {current},
            'Unexpected SD addition/removal')
    require({n for n in old_sd if sd[n] != old_sd[n]} == SD_CHANGED,
            'Unrelated SD changes')
    return new, sd, dict(previous_path=previous, path=current,
                         sha256=sha(new['alarm/driver.elf']), version='0.4.10')


def compose(a):
    require(not a.output.exists(), 'Output must be new')
    lock = json.loads(LOCK.read_bytes())
    clean_source(ROOT, a.product_revision, 'Product')
    require(git(ROOT, 'merge-base', lock['base_product'], a.product_revision) == lock['base_product'],
            'Product must descend from published .101')
    for name, pin in lock['sources'].items():
        root = getattr(a, name + '_source')
        commit = git(root, 'rev-parse', 'HEAD')
        require(commit in {pin['local_commit'], pin['published_commit']}, 'Wrong ' + name + ' commit')
        clean_source(root, commit, name)
        require(git(root, 'rev-parse', 'HEAD^{tree}') == pin['tree'], 'Wrong ' + name + ' tree')
    raw = (a.baseline / 'receipts/reader-files-composition.json').read_bytes()
    require(sha(raw) == lock['baseline_receipt_sha256'], 'Wrong .101 receipt')
    base = json.loads(raw)
    old, old_sd, parts = [read_tree(a.baseline / n) for n in ['store', 'SD', 'components']]
    previous = (a.baseline / 'X4-0.1.101-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
    require(sha(previous) == lock['baseline_image_sha256'] == base['full_image_sha256'], 'Wrong .101 BIN')
    require(base['product_source'] == lock['base_artifact_source'] and base['product_tree'] == lock['base_artifact_source_tree'],
            'Wrong delivered source identity')
    require(inventory(old) == base['store'] and inventory(old_sd) == base['sd'] and len(old) == 106 and len(old_sd) == 87,
            'Wrong baseline inventories')
    require(set(parts) == set(base['components']), 'Wrong baseline component set')
    for name, row in base['components'].items():
        data = parts[name]
        require(len(data) == row['bytes'] and sha(data) == row['sha256'] and
                previous[row['offset']:row['offset'] + len(data)] == data, 'Wrong component: ' + name)
    rf, rtc = checked_files(a.rf, lock['rf_files']), checked_files(a.rtc, lock['rtc_files'])
    require(json.loads(rf['build.json'])['waterfall']['sha256'] == sha(rf['waterfall.elf']), 'RF build differs')
    require(json.loads(rtc['receipts/x4-alarm-build.json'])['sha256'] == sha(rtc['x4/store/alarm/driver.elf']), 'Alarm build differs')
    home = json.loads(rtc['receipts/clock/committed-build.json'])
    require(not home['working_tree_dirty'] and home['sha256'] == sha(rtc['x4/store/default.elf']) and
            home['repository_commit'] == lock['sources']['alarm_system']['local_commit'], 'Home source custody differs')
    mapping = json.loads(rtc['receipts/clock/publication-build-mapping.json'])
    require(mapping['build']['target_bytes_identical_to_qualified_dirty_state_candidate'] and
            mapping['system']['published_tree'] == lock['sources']['alarm_system']['tree'], 'Home publication differs')
    new, sd, alarm = payload(old, old_sd, rf, rtc, a.product_revision)
    pack, decode, bank, parse = load_assembly_tools(a.tools, a.runtime_source)
    image, packing = ordered_build(new, pack)
    require(ordered_build(dict(reversed(list(new.items()))), pack) == (image, packing), 'Nondeterministic packing')
    previous_packing = json.loads((a.baseline / 'receipts/packing.json').read_bytes())
    for key in ['ordered_paths', 'order_recipe_sha256', 'generator_sha256', 'config', 'metadata', 'file_count', 'image_bytes']:
        require(packing[key] == previous_packing[key], 'Startup packing changed: ' + key)
    firmware = parts['firmware.bin']
    state = bank(firmware, image, True)
    full = bytearray(previous)
    full[slice(*BOOTFS)], full[slice(*BANK_STATE)] = image, state
    verify_image(bytes(full), previous, old, new, firmware, decode, parse)
    with tempfile.TemporaryDirectory(prefix='x4-102-selected-') as tmp:
        root = Path(tmp)
        write_files(root / 'store', new)
        write_files(root / 'SD', sd)
        selected = audit_selected_images(json.loads(new['boot.json']), root / 'store', root / 'SD')
    before = {r['manifest']: r for r in base['selected_sd_images']}
    after = {r['manifest']: r for r in selected}
    require(len(selected) == 48 and set(before) == set(after) and
            {n for n in before if before[n] != after[n]} == {'waterfall.json', 'alarm/manifest.json'},
            'Unrelated selected SD changes')
    require(after['alarm/manifest.json']['matches_internal_fallback'], 'Alarm SD/internal pair differs')
    overlay_paths = set(base['sd_overlay']['files']) | SD_CHANGED | {alarm['path']}
    overlay = {n: sd[n] for n in sorted(overlay_paths)}
    require(len(overlay) == 12, 'Wrong cumulative SD overlay')
    parts = dict(parts, **{'bootfs.bin': image, 'bank_state.bin': state})
    receipt = copy.deepcopy(base)
    receipt.pop('home_0_4_13_unchanged', None)
    receipt.update(schema='x4.evening-increment-composition', product_version=VERSION,
        product_source=a.product_revision, product_tree=git(ROOT, 'rev-parse', 'HEAD^{tree}'),
        product_base=lock['base_product'], baseline_full_image_sha256=lock['baseline_image_sha256'],
        baseline_receipt_sha256=lock['baseline_receipt_sha256'], recipe_sha256=sha(Path(__file__).read_bytes()),
        source_lock=lock, native_rebuilt=False, native_unchanged=True, store=inventory(new), sd=inventory(sd),
        selected_sd_images=selected, changed_store_paths=sorted(CHANGED), changed_sd_paths=sorted(SD_CHANGED),
        added_sd_files=[alarm['path']], original_sd_files_preserved=len(old_sd) - len(SD_CHANGED),
        boot_authority_unchanged=True, boot_image_selection_changed=[alarm], installation_envelope_unchanged=True,
        shared_settings_enabled=False, home_client=home, home_build=home,
        rf_build=json.loads(rf['build.json']), alarm_build=json.loads(rtc['receipts/x4-alarm-build.json']),
        components={n: dict(bytes=len(v), sha256=sha(v), offset=base['components'][n]['offset']) for n,v in parts.items()},
        packing_sha256=sha(encoded(packing)), full_image_bytes=len(full), full_image_sha256=sha(full),
        independent_full_image_verified=True, hardware_tested=False, target_instructions_executed=False,
        preserved_component_provenance=base['component_sources'], current_component_versions=lock['component_versions'],
        excluded=lock['excluded'])
    receipt['component_sources']['product_version'] = VERSION
    receipt['component_sources']['baseline_product'] = lock['base_product']
    for component, source in [('waterfall', 'rf_utilities'), ('home', 'alarm_system'), ('alarm-service', 'alarm_utilities')]:
        receipt['component_sources'][component] = dict(lock['sources'][source], version=lock['component_versions']['default' if component == 'home' else component])
    a.output.mkdir(parents=True)
    for name, files in [('store',new), ('SD',sd), ('components',parts)]:
        write_files(a.output / name, files)
    (a.output / IMAGE).write_bytes(full)
    with zipfile.ZipFile(a.output / ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in overlay.items():
            entry = zipfile.ZipInfo(name, (2026,10,12,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, data)
    with zipfile.ZipFile(a.output / ZIP) as z:
        require(z.testzip() is None and len(z.namelist()) == len(overlay) and
                {n: z.read(n) for n in z.namelist()} == overlay, 'SD overlay readback failed')
    receipt['sd_overlay'] = dict(name=ZIP, sha256=sha((a.output / ZIP).read_bytes()),
        files=inventory(overlay), cumulative_from_delivered_product='0.1.96',
        immediate_delta_from='0.1.101', immediate_delta_paths=sorted(SD_CHANGED | {alarm['path']}))
    write_files(a.output / 'receipts', {'evening-composition.json': encoded(receipt), 'packing.json': encoded(packing),
        'rf-build.json': rf['build.json'], 'alarm-build.json': rtc['receipts/x4-alarm-build.json'],
        'home-build.json': rtc['receipts/clock/committed-build.json'], 'rf-handoff.json': rf['handoff.json'],
        'rtc-handoff.json': rtc['handoff.json'], 'home-publication.json': rtc['receipts/clock/publication-build-mapping.json']})
    require(read_tree(a.output / 'store') == new and read_tree(a.output / 'SD') == sd and
            (a.output / IMAGE).read_bytes() == full, 'Output readback failed')
    print(json.dumps(dict(version=VERSION, sha256=sha(full), sd_files=len(overlay),
        native_unchanged=True, hardware_tested=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline', 'rf', 'rtc', 'runtime-source', 'rf-utilities-source', 'rf-system-source',
                 'alarm-utilities-source', 'alarm-system-source', 'tools', 'output']:
        parser.add_argument('--' + name, type=lambda v: Path(v).resolve(), required=True)
    parser.add_argument('--product-revision', required=True)
    compose(parser.parse_args())
