#!/usr/bin/env python3
"""Compose .90 from exact delivered .89 bytes and qualified rebuilt clients.

Offline only. No device access, credentials, firmware publication or release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE_RECEIPT = ROOT / 'minimal/docs/evidence/integration-089/qualification.json'
BASE_SD = ROOT / 'minimal/shared-settings-090-sd-baseline.json'
VERSIONS = {'default': '0.4.11', 'springboard': '1.8.4',
            'file_browser': '1.5.28', 'wifi_settings': '1.1.27', 'installed-apps': '0.9.0', 'contexts': '0.4.2'}
RECORDS = {'default': 'build-evidence.json', 'springboard': 'springboard-build-record.json',
           'file_browser': 'file_browser-build-record.json', 'wifi_settings': 'wifi_settings-build-record.json',
           'installed-apps': 'build.json', 'contexts': 'contexts-build-record.json'}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def tree(root):
    require(root.is_dir() and not root.is_symlink(), 'Expected real input directory')
    result = {}
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Symlinks are not composition inputs')
        if path.is_file():
            result[str(path.relative_to(root))] = sha(path)
    return result

def read(path):
    return json.loads(path.read_text())

def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()

def resolved_grants(requests, policy):
    # Runtime::acquire resolves selector zero only when the app's own policy
    # contains one matching capability/API. Never choose the first provider.
    resolved = []
    for request in requests:
        matches = [row for row in policy if row['capability'] == request['capability'] and
                   row['api'] == request['api'] and
                   (not request['instance_id'] or row['instance_id'] == request['instance_id'])]
        require(len(matches) == 1, 'Files 16-grant selector is missing or ambiguous')
        resolved.append(matches[0])
    return resolved

def select_provider_images(boot, store, sd):
    # Delivered .89 had two stale preferred SD images despite updated internal
    # fallbacks. Preserve those immutable files, but never select them in .90.
    repaired = []
    for row in boot['drivers']:
        source = row.get('image_source')
        if not source:
            continue
        manifest = read(store / row['manifest'])
        native = store / Path(row['manifest']).parent / manifest['file_name']
        selected = sd / source['path']
        require(source.get('internal_fallback') is True and source['volume_instance'] == 9,
                'Unexpected selected provider source policy')
        if sha(selected) != sha(native):
            require(row['manifest'] in ('wifi/manifest.json', 'sharing-ble/manifest.json'),
                    'Unexpected selected SD provider mismatch')
            previous = source['path']
            source['path'] = str(Path(previous).parent / ('image-' + sha(native) + '.elf'))
            target = sd / source['path']
            require(not target.exists() or target.read_bytes() == native.read_bytes(),
                    'Immutable provider image collision')
            shutil.copyfile(native, target)
            repaired.append(dict(manifest=row['manifest'], previous=previous, selected=source['path']))
    return repaired

def audit_selected_images(boot, store, sd):
    rows = []
    for kind in ('drivers', 'app_capabilities'):
        for row in boot[kind]:
            source = row.get('image_source')
            if not source:
                continue
            manifest = read(store / row['manifest'])
            selected = sd / source['path']
            if kind == 'drivers':
                fallback = store / Path(row['manifest']).parent / manifest['file_name']
                require(selected.read_bytes() == fallback.read_bytes(), 'Selected provider differs from qualified fallback')
            else:
                require(read(selected.parent / 'manifest.json') == manifest, 'Selected SD application manifest differs')
            rows.append(dict(role='driver' if kind == 'drivers' else 'app', manifest=row['manifest'],
                             path=source['path'], sha256=sha(selected), size_bytes=selected.stat().st_size,
                             matches_internal_fallback=kind == 'drivers'))
    return rows

def validate_module(name, directory, base, system, runtime, utilities=None):
    manifest_name = 'manifest.json' if name == 'installed-apps' else name + '.json'
    elf_name = 'driver.elf' if name == 'installed-apps' else name + '.elf'
    old = base / ('installed-apps' if name == 'installed-apps' else '') / manifest_name
    manifest, previous = read(directory / manifest_name), read(old)
    require(manifest.get('version') == VERSIONS[name], 'Wrong selected version: ' + name)
    expected_manifest = dict(previous)
    if name == 'file_browser':
        expected_manifest['requires'] = [x for x in previous['requires'] if x['capability'] != 'storage.app-data.export']
        expected_manifest['requires'].append({'capability': 'bluetooth.hci', 'api': 1})
    require({k: v for k, v in manifest.items() if k not in ('version', 'requires')} ==
            {k: v for k, v in previous.items() if k not in ('version', 'requires')} and
            sorted(manifest['requires'], key=lambda x: (x['capability'], x['api'])) ==
            sorted(expected_manifest['requires'], key=lambda x: (x['capability'], x['api'])),
            'Manifest authority changed: ' + name)
    receipt = read(directory / RECORDS[name])
    require(receipt.get('elf_sha256', receipt.get('sha256')) == sha(directory / elf_name),
            'Build receipt does not identify ELF: ' + name)
    if name == 'installed-apps':
        repos = receipt.get('repositories', {})
        require(any(v.get('head') == system and not v.get('dirty') for v in repos.values()),
                'Catalog System source missing or dirty')
        require(any(v.get('head') == runtime and not v.get('dirty') for v in repos.values()),
                'Catalog Runtime source missing or dirty')
        require(receipt.get('shared_settings_sd') is True and receipt.get('shared_settings_root') == '/RTECFG',
                'Catalog cannot restore shared settings')
    elif name == 'contexts':
        repos=receipt.get('repositories', {})
        require(all(repos.get(key)==dict(head=head,dirty=False) for key,head in [('system',system),('runtime',runtime),('utilities',utilities)]), 'Contexts exact source missing or dirty')
        require(receipt.get('catalog_count') == 26 and receipt.get('catalog_sha256') == sha(ROOT/'minimal/contexts-090-catalog.json') and receipt.get('face_header') is None, 'Contexts complete catalog or face profile differs')
        require(receipt.get('target_build',{}).get('sha256') == sha(directory / elf_name), 'Contexts target receipt mismatch')
    else:
        require(receipt.get('repository_commit') == system and receipt.get('working_tree_dirty') is False,
                'Client source missing or dirty: ' + name)
    if name in ('default', 'springboard'):
        require(receipt.get('installed_catalog', {}).get('idle_settings_maintenance') == 'settings_pending-v1',
                'Client lacks continuing checkpoint maintenance: ' + name)
        require(receipt['installed_catalog'].get('volume_instance') == 9, 'Catalog volume changed')
    if name == 'default':
        require(receipt.get('installed_catalog', {}).get('alarm_reconcile_waits_for_shared_preferences') is True,
                'Cold alarm reconciliation must wait for restored preferences')
        flags = receipt.get('build_defines', [])
        for flag in ('-DPORTABLE_DESK_LOCK_HOME', '-DPORTABLE_DESK_POINTS_SNAPSHOT',
                     '-DPORTABLE_RESIDENT_SHELL_HOST'):
            require(flag in flags, 'Required Home profile flag missing: ' + flag)
        require(receipt.get('sparse_start') is True and receipt.get('desk_points', {}).get('retained_bytes') == 408,
                'Home retained profile changed')
    if name == 'file_browser':
        require(receipt.get('file_sharing', {}).get('app_data_export_required') is False,
                'Volume-only Files must not acquire the unused export grant')
        protection = receipt.get('protected_settings', {})
        sharing = receipt.get('file_sharing', {})
        require(protection.get('root') == '/RTECFG' and protection.get('listing_open_mutation_copy') is True,
                'Files protected settings guard missing')
        require(sharing.get('protected_settings', {}).get('direct_recursive_and_peer') is True and
                sharing.get('default_transport') == 'ble-private-wifi' and sharing.get('peer_files') is True,
                'Direct private network, recursive or peer protection missing')
    if name == 'wifi_settings':
        require('-DPORTABLE_WIFI_PROFILES' in receipt.get('build_defines', []), 'Growing Wi-Fi profiles missing')
    return manifest_name, elf_name, receipt

def compose(base, sd, modules, output, system, runtime, namespaces, utilities=None):
    require(not output.exists(), 'Output must be new')
    require(namespaces == [], 'Shared settings remain disabled until native fallback and reconciliation qualify')
    expected = read(BASE_RECEIPT)
    require(tree(base) == expected['store'], 'Base is not the exact complete delivered .89 store')
    sd_inventory = tree(sd)
    require(sd_inventory == read(BASE_SD)['files'], 'Base is not the exact complete delivered .89 SD set')
    records = {name: validate_module(name, directory, base, system, runtime, utilities) for name, directory in modules.items()}
    boot = read(base / 'boot.json')
    require(len(boot['app_capabilities']) == 26 and len(boot['drivers']) == 32, 'Incomplete base profile')
    install = boot['installation']
    require(install.get('settings_sd') is True and install.get('volume_instance') == 9 and
            install.get('namespace_range') == {'first': 3000, 'count': 128} and not install.get('shared_settings'),
            'Unexpected installed settings authority')
    # The SD-first candidate is deliberately not opted into this product.
    # Cold-card absence must not make ordinary preferences/apps unavailable.
    require('shared_settings' not in install, 'Unexpected active shared settings policy')
    files_policy = next(x for x in boot['app_capabilities'] if x['manifest'] == 'file_browser.json')
    old_grants = files_policy['grants']
    require(len(old_grants) == 16 and sum(x['capability'] == 'storage.app-data.export' for x in old_grants) == 1,
            'Unexpected Files grant baseline')
    require(files_policy.get('app_data_export') == {'label': 'Saved files', 'files': [
        {'owner': 'timecard', 'namespace': 1, 'name': 'timecard.json',
         'path': '/timecard/timecard.json', 'access': 'read-write'}]}, 'Unexpected unused Files export map')
    # The volume-only client cannot use this projection. Runtime rejects a map
    # without its corresponding grant, so remove both as one authority change.
    del files_policy['app_data_export']
    files_policy['grants'] = [x for x in old_grants if x['capability'] != 'storage.app-data.export']
    files_policy['grants'].append({'capability': 'bluetooth.hci', 'api': 1, 'instance_id': 16})
    keys = lambda rows: sorted((x['capability'], x['api'], x['instance_id']) for x in rows)
    require(keys(resolved_grants(records['file_browser'][2]['required_grants'], files_policy['grants'])) == keys(files_policy['grants']) and
            len(files_policy['grants']) == 16, 'Files receipt must prove the exact 16-grant substitution')
    catalog = next(x for x in boot['drivers'] if x['manifest'] == 'installed-apps/manifest.json')
    require(catalog.get('image_source', {}).get('internal_fallback') is True and
            catalog['image_source']['volume_instance'] == 9, 'Catalog fallback authority differs')
    catalog['image_source']['path'] = 'Drivers/installed-apps/image-' + sha(modules['installed-apps'] / 'driver.elf') + '.elf'
    shutil.copytree(base, output / 'store')
    shutil.copytree(sd, output / 'SD')
    (output / 'receipts').mkdir()
    for name, directory in modules.items():
        manifest, elf, receipt = records[name]
        target = output / 'store' / ('installed-apps' if name == 'installed-apps' else '')
        for filename in ((manifest,) if name == 'contexts' else (manifest, elf)):
            shutil.copyfile(directory / filename, target / filename)
        (output / 'receipts' / (name + '-build.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    target = output / 'SD' / catalog['image_source']['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(modules['installed-apps'] / 'driver.elf', target)
    contexts=next(x for x in boot['app_capabilities'] if x['manifest']=='contexts.json')
    require(contexts.get('image_source') == dict(volume_instance=9,path='Apps/contexts/contexts.elf'), 'Unexpected Contexts source policy')
    contexts['image_source']['path']='Apps/contexts/image-'+sha(modules['contexts']/'contexts.elf')+'/contexts.elf'
    ctx_target=output/'SD'/contexts['image_source']['path'];ctx_target.parent.mkdir(parents=True)
    shutil.copyfile(modules['contexts']/'contexts.elf',ctx_target)
    shutil.copyfile(modules['contexts']/'contexts.json',ctx_target.parent/'manifest.json')
    repaired_sources = select_provider_images(boot, output / 'store', output / 'SD')
    selected_images = audit_selected_images(boot, output / 'store', output / 'SD')
    cohort = read(output / 'store/cohort.json'); cohort['version'] = '0.1.90'
    (output / 'store/cohort.json').write_text(json.dumps(cohort, indent=2) + '\n')
    (output / 'store/boot.json').write_text(json.dumps(boot, indent=2) + '\n')
    # Every old SD file remains byte-identical, including old immutable provider
    # images. Only the new catalog image is added; never copy live settings.
    actual_sd = tree(output / 'SD')
    require(all(actual_sd.get(n) == digest for n, digest in sd_inventory.items()), 'An old SD file changed')
    actual_store = tree(output / 'store')
    changed = {n for n in actual_store if actual_store[n] != expected['store'].get(n)}
    allowed = {'boot.json', 'cohort.json'} | {('installed-apps/' if n == 'installed-apps' else '') + f
                              for n, (m, e, _) in records.items() for f in ((m,) if n == 'contexts' else (m, e))}
    require(set(actual_store) == set(expected['store']) and changed <= allowed, 'Unexpected store changes')
    result = dict(product_version='0.1.90', runtime_commit=runtime, system_commit=system, utilities_commit=utilities,
                  repaired_sd_provider_sources=repaired_sources, selected_sd_images=selected_images,
                  shared_settings=namespaces, shared_settings_enabled=False,
                  persistence_status='unfinished: native fallback and returning-card reconciliation required', native_build_required=True,
                  required_native_options=dict(retained_wake_bytes=512, usb_phy=True, provider_capacity=40,
                                               installed_app_capacity=64, app_policy_rows=24, app_requirement_rows=24,
                                               shared_files_transport=True, app_image_cache=False),
                  changed_store_paths=sorted(changed), preserved_store_files=len(actual_store) - len(changed),
                  preserved_sd_files=len(sd_inventory), added_sd_files=sorted(set(actual_sd)-set(sd_inventory)),
                  full_initial_image_erases_internal_data=True, hardware_tested=False, flashable=False,
                  confidentiality='Plaintext removable-card recovery. Files/WebDAV exclusions do not protect physical card access or raw USB export.')
    (output / 'receipts/shared-settings-composition.json').write_text(json.dumps(result, indent=2) + '\n')
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base-store', 'base-sd', 'home', 'springboard', 'files', 'wifi', 'catalog', 'contexts', 'output', 'system-source', 'runtime-source', 'utilities-source'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for root in (args.system_source, args.runtime_source, args.utilities_source):
        require(not git(root, 'status', '--porcelain', '--untracked-files=normal'), 'Clean committed sources required')
    modules = dict(default=args.home, springboard=args.springboard, file_browser=args.files,
                   wifi_settings=args.wifi, contexts=args.contexts, **{'installed-apps': args.catalog})
    print(json.dumps(compose(args.base_store, args.base_sd, modules, args.output,
                             git(args.system_source, 'rev-parse', 'HEAD'), git(args.runtime_source, 'rev-parse', 'HEAD'), [], git(args.utilities_source, 'rev-parse', 'HEAD')), indent=2))

if __name__ == '__main__':
    main()
