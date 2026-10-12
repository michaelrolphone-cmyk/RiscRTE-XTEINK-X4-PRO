#!/usr/bin/env python3
"""Compose Files shared plaintext entry over the qualified X4 .102 cohort."""
import argparse, copy, json, tempfile, zipfile
from pathlib import Path, PurePosixPath
from compose_desk_wake_093 import read_tree, clean_source
from compose_files_092 import require, sha, encoded, inventory, git, write_files, load_assembly_tools, BOOTFS, BANK_STATE
from compose_keyboard_100 import verify_image
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build

ROOT = Path(__file__).resolve().parents[2]
BASE = '918f3aa7d30ae5e853ff4251c6aa89c6d0f22586'
SYSTEM = 'e3fd26c2257cef91c8f6a7b98065b52f1db7a54d'
SYSTEM_TREE = '05ca25fa292f9420a32743b1468f7efee6d2fc78'
IMAGE = 'X4-0.1.102-FULL-INITIAL-ERASES-DATA.bin'
ZIP = 'X4-0.1.102-Combined-Changed-SD.zip'
GRANT = dict(capability='ui.text-input', api=1, instance_id=0)
CHANGED = {'file_browser.elf', 'file_browser.json', 'ui-scene/driver.elf',
           'ui-scene/manifest.json', 'ui-text/driver.elf', 'ui-text/manifest.json',
           'boot.json', 'cohort.json'}

def component(files, hosts):
    f = json.loads((files / 'file_browser-build-record.json').read_bytes())
    h = json.loads((hosts / 'hosts-build-record.json').read_bytes())
    require(f['repository_commit'] == SYSTEM and not f['working_tree_dirty'] and f['version'] == '1.5.34', 'Wrong Files source')
    require(f['profile'] == 'x4-native-time' and f['grant_count'] == 17, 'Wrong X4 Files profile')
    data = {n: (files / n).read_bytes() for n in ['file_browser.elf', 'file_browser.json']}
    require(sha(data['file_browser.elf']) == f['sha256'] and len(data['file_browser.elf']) == f['size_bytes'], 'Files custody differs')
    for key, dest, version in [('scene', 'ui-scene', '0.4.4'), ('text', 'ui-text', '0.1.5')]:
        r = h[key]
        require(r['system_commit'] == SYSTEM and r['system_tree'] == SYSTEM_TREE and not r['working_tree_dirty'], 'Host source differs')
        require(r['version'] == version and not r['defines'], 'Wrong X4 full host profile')
        for name in ['driver.elf', 'manifest.json']:
            data[dest + '/' + name] = (hosts / key / name).read_bytes()
        require(sha(data[dest + '/driver.elf']) == r['sha256'] and len(data[dest + '/driver.elf']) == r['size_bytes'], 'Host custody differs')
    return data, f, h

def payload(old, old_sd, components, revision):
    new, sd = dict(old, **components), dict(old_sd)
    expected = json.loads(old['file_browser.json'])
    require(expected['version'] == '1.5.32', 'Wrong Files predecessor')
    expected['version'] = '1.5.34'; expected['requires'].append(dict(capability='ui.text-input', api=1))
    require(json.loads(new['file_browser.json']) == expected, 'Files authority exceeds additive grant')
    for name, version in [('ui-scene/manifest.json', '0.4.4'), ('ui-text/manifest.json', '0.1.5')]:
        require(json.loads(new[name]) == dict(json.loads(old[name]), version=version), 'Host authority changed')
    boot = json.loads(old['boot.json']); original = copy.deepcopy(boot)
    rows = [r for r in boot['app_capabilities'] if r['manifest'] == 'file_browser.json']
    require(len(rows) == 1 and GRANT not in rows[0]['grants'] and len(rows[0]['grants']) == 16, 'Unexpected Files authority')
    rows[0]['grants'].append(copy.deepcopy(GRANT))
    selections = []
    for directory in ['ui-scene', 'ui-text']:
        row = next(r for r in boot['drivers'] if r['manifest'] == directory + '/manifest.json')
        source = row['image_source']; previous = source['path']
        require(source['internal_fallback'] is True and source['volume_instance'] == 9, 'Host fallback authority differs')
        require(old_sd[previous] == old[directory + '/driver.elf'], 'Stale baseline SD host')
        raw = new[directory + '/driver.elf']
        current = str(PurePosixPath(previous).parent / ('image-' + sha(raw) + '.elf'))
        require(current not in old_sd, 'Immutable host collision')
        source['path'] = current; sd[current] = raw
        selections.append(dict(manifest=row['manifest'], previous_path=previous, path=current, sha256=sha(raw)))
    restored = copy.deepcopy(boot)
    next(r for r in restored['app_capabilities'] if r['manifest'] == 'file_browser.json')['grants'].pop()
    for selection in selections:
        next(r for r in restored['drivers'] if r['manifest'] == selection['manifest'])['image_source']['path'] = selection['previous_path']
    require(restored == original, 'Unrelated boot authority changed')
    new['boot.json'] = encoded(boot)
    cohort = json.loads(old['cohort.json'])
    require(cohort['version'] == '0.1.102' and cohort['source_revision'] == BASE and cohort['runtime_version'] == '0.2.28', 'Wrong baseline')
    cohort['source_revision'] = revision; new['cohort.json'] = encoded(cohort)
    require(set(new) == set(old) and {n for n in new if new[n] != old[n]} == CHANGED, 'Unexpected store delta')
    require(set(sd) - set(old_sd) == {r['path'] for r in selections} and all(sd[n] == raw for n,raw in old_sd.items()), 'Existing SD data changed')
    return new, sd, selections

def compose(a):
    require(not a.output.exists(), 'Output must be new')
    revision = git(ROOT, 'rev-parse', 'HEAD'); clean_source(ROOT, revision, 'Product')
    raw = (a.baseline / 'receipts/evening-composition.json').read_bytes(); base = json.loads(raw)
    require(base['product_source'] == BASE, 'Wrong baseline recipe')
    clean_source(a.runtime, base['runtime_commit'], 'Runtime')
    require(git(a.runtime, 'rev-parse', 'HEAD^{tree}') == base['runtime_tree'], 'Runtime tree differs')
    old, old_sd, parts = [read_tree(a.baseline / n) for n in ['store', 'SD', 'components']]
    previous = (a.baseline / IMAGE).read_bytes()
    require(sha(previous) == base['full_image_sha256'], 'Wrong baseline BIN')
    require(inventory(old) == base['store'] and inventory(old_sd) == base['sd'] and len(old) == 106 and len(old_sd) == 88, 'Wrong baseline inventory')
    require(set(parts) == set(base['components']), 'Wrong components')
    for name, row in base['components'].items():
        data = parts[name]
        require(len(data) == row['bytes'] and sha(data) == row['sha256'] and previous[row['offset']:row['offset'] + len(data)] == data, 'Wrong component: ' + name)
    components, files, hosts = component(a.files_build, a.hosts_build)
    new, sd, selections = payload(old, old_sd, components, revision)
    pack, decode, bank, parse = load_assembly_tools(a.tools, a.runtime)
    image, packing = ordered_build(new, pack)
    require(ordered_build(dict(reversed(list(new.items()))), pack) == (image, packing), 'Nondeterministic packing')
    prior_packing = json.loads((a.baseline / 'receipts/packing.json').read_bytes())
    for key in ['ordered_paths', 'order_recipe_sha256', 'generator_sha256', 'config', 'metadata', 'file_count', 'image_bytes']:
        require(packing[key] == prior_packing[key], 'Startup packing changed: ' + key)
    require(packing['empty_blocks'] >= 2, 'Store reserve violated')
    firmware = parts['firmware.bin']; state = bank(firmware, image, True)
    full = bytearray(previous); full[slice(*BOOTFS)], full[slice(*BANK_STATE)] = image, state
    verify_image(bytes(full), previous, old, new, firmware, decode, parse)
    with tempfile.TemporaryDirectory(prefix='x4-files-shared-') as tmp:
        root = Path(tmp); write_files(root / 'store', new); write_files(root / 'SD', sd)
        selected = audit_selected_images(json.loads(new['boot.json']), root / 'store', root / 'SD')
    before = {r['manifest']: r for r in base['selected_sd_images']}; after = {r['manifest']: r for r in selected}
    changed_hosts = {s['manifest'] for s in selections}
    require(len(selected) == 48 and set(before) == set(after) and {n for n in before if before[n] != after[n]} == changed_hosts, 'Unrelated selected SD changes')
    require(all(after[n]['matches_internal_fallback'] for n in changed_hosts), 'SD/internal host pair differs')
    overlay_paths = set(base['sd_overlay']['files']) | {r['path'] for r in selections}
    overlay = {n: sd[n] for n in sorted(overlay_paths)}; require(len(overlay) == 14, 'Wrong cumulative SD overlay')
    parts.update({'bootfs.bin': image, 'bank_state.bin': state})
    receipt = copy.deepcopy(base); receipt.pop('files_1_5_31_unchanged', None)
    receipt.update(schema='x4.files-shared-input-composition', product_source=revision, product_tree=git(ROOT, 'rev-parse', 'HEAD^{tree}'),
        product_base=BASE, baseline_full_image_sha256=sha(previous), baseline_receipt_sha256=sha(raw),
        recipe_sha256=sha(Path(__file__).read_bytes()), store=inventory(new), sd=inventory(sd), selected_sd_images=selected,
        changed_store_paths=sorted(CHANGED), changed_sd_paths=[], added_sd_files=[r['path'] for r in selections],
        original_sd_files_preserved=len(old_sd), boot_authority_unchanged=False,
        boot_authority_delta=[dict(manifest='file_browser.json', grant=GRANT)], boot_image_selection_changed=selections,
        files_build=files, files_client=files, scene_build=hosts['scene'], text_build=hosts['text'],
        components={n: dict(bytes=len(v), sha256=sha(v), offset=base['components'][n]['offset']) for n,v in parts.items()},
        packing_sha256=sha(encoded(packing)), full_image_bytes=len(full), full_image_sha256=sha(full),
        current_component_versions=dict(base['current_component_versions'], files='1.5.34', scene_host='0.4.4', text_input_host='0.1.5'),
        system_commit=SYSTEM, system_tree=SYSTEM_TREE, native_rebuilt=False, native_unchanged=True,
        independent_full_image_verified=True, hardware_tested=False, target_instructions_executed=False,
        delivered=False, delivery_hold_until_utc='2026-10-12T23:30:00Z')
    receipt['component_sources'] = copy.deepcopy(base['component_sources'])
    for key, version in [('files','1.5.34'), ('scene-host','0.4.4'), ('text-input-host','0.1.5')]:
        receipt['component_sources'][key] = dict(repository='michaelrolphone-cmyk/RiscRTE-System-Apps', commit=SYSTEM, tree=SYSTEM_TREE, version=version)
    a.output.mkdir(parents=True)
    for name, items in [('store',new), ('SD',sd), ('components',parts)]: write_files(a.output / name, items)
    (a.output / IMAGE).write_bytes(full)
    with zipfile.ZipFile(a.output / ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in overlay.items():
            entry = zipfile.ZipInfo(name, (2026,10,12,0,0,0)); entry.compress_type = zipfile.ZIP_DEFLATED; entry.external_attr = 0o100644 << 16
            z.writestr(entry, data)
    with zipfile.ZipFile(a.output / ZIP) as z:
        require(z.testzip() is None and len(z.namelist()) == len(overlay) and {n: z.read(n) for n in z.namelist()} == overlay, 'SD overlay readback differs')
    receipt['sd_overlay'] = dict(name=ZIP, sha256=sha((a.output / ZIP).read_bytes()), files=inventory(overlay),
        cumulative_from_delivered_product='0.1.96', immediate_delta_from='0.1.102 evening candidate', immediate_delta_paths=[r['path'] for r in selections])
    write_files(a.output / 'receipts', {'evening-composition.json':encoded(receipt), 'packing.json':encoded(packing), 'files-build.json':encoded(files), 'hosts-build.json':encoded(hosts)})
    require(read_tree(a.output / 'store') == new and read_tree(a.output / 'SD') == sd and (a.output / IMAGE).read_bytes() == full, 'Output readback differs')
    print(json.dumps(dict(sha256=sha(full), sd_overlay_files=len(overlay), free_blocks=packing['empty_blocks'], native_unchanged=True, hardware_tested=False)))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ['baseline','files-build','hosts-build','runtime','tools','output']:
        p.add_argument('--' + n, type=lambda v: Path(v).resolve(), required=True)
    compose(p.parse_args())
