#!/usr/bin/env python3
"""Build an X4 canonical payload pair, never publish, associate or operate a device.

prepare: audit the frozen .123 factory / 77-file SD baseline and emit an explicitly
synthetic, non-installable fixture. It is not a .124 release or qualification.
prepare-candidate: schema-test actual qualified .124 bytes with explicitly
synthetic release identity. This is still NONINSTALLABLE, never a release.
finalize: require exact .124 qualified bytes, a live public GitHub release,
a fresh catalog readback, installed-bootstrap evidence, and an independently
reviewed trusted validation context. No release ID/revision defaults exist.

Finalization emits only a LOCAL descriptor candidate. Publication authorization,
asset upload/readback and catalog association are separate, unchanged gates.
The context supplied to finalize must come from independent review, not from
blindly trusting this tool's manifest. All plans are explicit create/replace
operations, not extraction, directory replacement or firmware-over-RTEF1.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import stat
import sys
from datetime import datetime, timezone
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/native-paired-124/payload-contract.json'
REPOSITORY = 'michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO'
VERSION = '0.1.124'
TAG = 'test-native-paired-0.1.124'
BOOTSTRAP = 'test-native-provision-0.1.123'
FACTORY = 'factory-candidate-erases-data-0x0.bin'
SD_ARCHIVE = 'X4-0.1.124-Complete-SD-Keep-Existing.zip'
VOLUME = 'application-content'
OWNER = 'x4-boot-owned-external-content'
SCHEMA_REVISION = '908355b0509907c05a6dc47a1ccc8e078d6e23b0'
SCHEMA_HASHES = {
    'validate.py': '57f5803a8d98287a9a0f5e2aa7fdb92d63d6b0775763f48f08d8a79ca1fbfac4',
    'manifest.schema.json': '735c3895826bcec9feba7cc8b4cd10d6610cbeae8d011e398287aa885daf4333',
    'context.schema.json': 'd27f1039828391a836d4e3c9b3ad43ff008112a1e2b2fd305894ade74466ce16',
    'descriptor.schema.json': '105cea7dc6436b780f7ebc3e21be58cacd47d1feb028cddf3ff054032ef3a96e',
}
NATIVE_MARKER = 'X4_VERSION=0.1.124-paired-candidate'
RUNTIME_REVISION = '6a3b3d46f5b2857eacc6e9863799dec1f466b036'
MAX_PAYLOAD_BYTES = 128 * 1024 * 1024
MAX_FILES = 4096
POLICY = {
    'completion': 'all-required-files-readable-by-target-consumer',
    'on_partial_file': 'retain-and-reconcile-selected-file',
    'on_uncertain_result': 'stop-inspect-no-automatic-retry',
    'replacement': 'explicit-selected-file-in-place-nonatomic', 'rollback': 'none',
    'unrelated_files': 'preserve', 'verification': 'commit-crc32-then-full-sha256-readback',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    return {'bytes': len(data), 'sha256': sha(data)}


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON member: ' + key)
        result[key] = value
    return result


def parse(data):
    require(len(data) <= 8 * 1024 * 1024, 'Metadata exceeds bound')
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def regular_bytes(path, limit):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), 'Expected regular file: ' + str(path))
    require(path.stat().st_size <= limit, 'Input exceeds bound: ' + str(path))
    with path.open('rb') as source:
        data = source.read(limit + 1)
    require(len(data) <= limit, 'Input exceeds bound: ' + str(path))
    return data


def load_json(path):
    require(path is not None, 'Required evidence file is missing')
    return parse(regular_bytes(path, 8 * 1024 * 1024))


def schema_module(directory):
    directory = Path(directory)
    for name, digest in SCHEMA_HASHES.items():
        require(sha(regular_bytes(directory / name, 1024 * 1024)) == digest,
                'Frozen schema differs at ' + SCHEMA_REVISION + ': ' + name)
    spec = importlib.util.spec_from_file_location('x4_exact_payload_schema', directory / 'validate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checked_destination(name):
    require(isinstance(name, str) and name and name.isascii(), 'Payload path must be exact ASCII')
    require(not name.startswith('/') and not name.endswith('/'), 'Payload path must be a relative file')
    parts = name.split('/')
    require(all(p and p not in ('.', '..') and not p.endswith((' ', '.')) for p in parts), 'Unsafe payload path')
    require(not any(ord(c) < 32 or ord(c) == 127 or c in ':\\*?"<>|' for c in name), 'Unsafe payload character')
    require(len(('/' + name).encode()) <= 511 and all(len(p.encode()) <= 127 for p in parts), 'Payload path exceeds provider bound')
    require(parts[0] in ('Apps', 'Drivers', 'fonts'), 'Only declared external content roots are writable')
    # No generic boot/internal namespace, immutable boot.json/store or whole-tree write.
    require(not any(p.lower() in ('boot.json', 'store.bin', 'firmware.bin') for p in parts), 'Immutable boot write forbidden')
    return parts


def read_payload(path):
    raw = regular_bytes(path, MAX_PAYLOAD_BYTES)
    files = {}
    aliases = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        require(0 < len(rows) <= MAX_FILES, 'Payload inventory count outside bounds')
        require(sum(r.file_size for r in rows) <= MAX_PAYLOAD_BYTES, 'Expanded payload exceeds bound')
        for row in rows:
            name = row.filename
            checked_destination(name)
            require(name == row.orig_filename, 'Truncated or ambiguous ZIP path')
            require(name.lower() not in aliases, 'Duplicate or case-aliased payload path')
            aliases.add(name.lower())
            mode = row.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not row.is_dir(), 'Payload member is not a regular file')
            require(not row.flag_bits & 1, 'Encrypted payload unsupported')
            require(row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'Unsupported input compression')
            files[name] = archive.read(row)
    # A file cannot also serve as a directory, including a case-only alias.
    for name in files:
        parts = name.split('/')
        require(not any('/'.join(parts[:i]).lower() in aliases for i in range(1, len(parts))), 'File/directory collision')
    return raw, files


def checked_inventory(files, expected):
    require(isinstance(expected, dict) and set(files) == set(expected), 'Missing or extra payload file')
    for name, data in files.items():
        row = expected[name]
        require(type(row.get('bytes')) is int and row['bytes'] == len(data) and row.get('sha256') == sha(data),
                'Changed payload file: ' + name)


def check_baseline(factory, archive, files):
    contract = load_json(CONTRACT)
    require(record(factory) == contract['baseline']['factory'], 'Fixture factory differs from published .123 bytes')
    require(record(archive) == contract['baseline']['sd_archive'], 'Fixture SD archive differs from published baseline bytes')
    checked_inventory(files, contract['baseline']['payload_files'])
    return contract


def check_qualification(admission, qualification, raw, factory, archive, files, require_hardware_revision=True):
    require(admission.get('version') == VERSION and admission.get('release_tag') == TAG, 'Exact qualified .124 identity required')
    require(admission.get('native_marker') == NATIVE_MARKER and NATIVE_MARKER.encode() in factory,
            'Qualified .124 native marker missing')
    require(len(factory) == 16 * 1024 * 1024 and record(factory) == admission['factory'], 'Qualified factory differs')
    require(record(archive) == admission['sd_archive'], 'Qualified SD archive differs')
    require(record(raw) == admission['qualification'], 'Exact qualification evidence differs')
    checked_inventory(files, admission['payload_files'])
    commit = admission['source_commit']
    require(isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit), 'Immutable product source required')
    lock = qualification['input_lock']
    require(lock['candidate_version'] == VERSION and lock['sources']['product']['revision'] == commit,
            'Qualification source/version differs')
    require(lock['sources']['runtime']['revision'] == admission['runtime_revision'] == RUNTIME_REVISION, 'Qualified runtime differs')
    require(qualification['status'] == 'software-qualified-candidate-hardware-pending', 'Successful software qualification required')
    require(qualification['artifacts'][FACTORY] == record(factory) and
            qualification['artifacts'][SD_ARCHIVE] == record(archive), 'Qualification artifact identity differs')
    native = qualification['artifacts']['firmware.bin']
    require(type(native['bytes']) is int and 0 < native['bytes'] <= 0x260000, 'Invalid qualified native size')
    embedded = factory[0x10000:0x10000 + native['bytes']]
    require(record(embedded) == native and NATIVE_MARKER.encode() in embedded, 'Qualified native identity differs inside factory')
    require(set(re.findall(rb'X4_SOURCE=([^\x00\s]+)', embedded)) == {commit.encode()}, 'Embedded native product source differs or is ambiguous')
    require(set(re.findall(rb'RTE_SOURCE=([^\x00\s]+)', embedded)) == {admission['runtime_revision'].encode()}, 'Embedded native runtime source differs or is ambiguous')
    checked_inventory(files, qualification['sd_preservation']['files'])
    for key in ('admission', 'admission_sanitized'):
        mapping = qualification[key]['retained_sd_graph_binding']
        require(mapping['provider'] == 'x4pro-sd' and type(mapping['instance']) is int and mapping['instance'] == 9 and
                type(mapping['wire_namespace']) is int and mapping['wire_namespace'] == 12 and
                mapping['production_graph_binding_passed'] is True, 'Qualified wire12/provider9 mapping required')
    require(admission['product_id'] == 'xteink-x4-pro', 'Wrong product identity')
    require(admission['hardware_profile'] == 'x4', 'Wrong hardware profile')
    if require_hardware_revision:
        revision = admission.get('hardware_revision')
        require(isinstance(revision, str) and revision and not revision.startswith('fixture'), 'Exact independently admitted board revision required')


def release_identity(metadata, admission):
    rid = metadata.get('id')
    require(type(rid) is int and rid > 1, 'Actual nonsynthetic numeric GitHub release ID required')
    require(metadata.get('draft') is False and metadata.get('prerelease') is True and metadata.get('published_at'),
            'Exact public prerelease required')
    require(metadata.get('tag_name') == TAG and metadata.get('target_commitish') == admission['source_commit'],
            'Release source/tag differs from qualified .124')
    require(metadata.get('url') == 'https://api.github.com/repos/' + REPOSITORY + '/releases/' + str(rid),
            'Wrong GitHub release API identity')
    require(metadata.get('html_url') == 'https://github.com/' + REPOSITORY + '/releases/tag/' + TAG,
            'Wrong release repository')
    return str(rid)


def live_release(recorded):
    """Read-only official API verification; no caller-provided endpoint or auth."""
    url = 'https://api.github.com/repos/' + REPOSITORY + '/releases/' + str(recorded['id'])
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'x4-pair-validator'})
    with urllib.request.urlopen(request, timeout=30) as response:
        require(response.url == url, 'Release metadata redirect not accepted')
        raw = response.read(8 * 1024 * 1024 + 1)
    actual = parse(raw)
    require(actual == recorded, 'Saved release metadata is stale or differs from live GitHub')
    return actual


def verify_public_assets(metadata, admission):
    rows = metadata['assets']
    require(len({r['name'] for r in rows}) == len(rows) and len({r['id'] for r in rows}) == len(rows),
            'Ambiguous public asset identity')
    assets = {r['name']: r for r in rows}
    base = 'https://github.com/' + REPOSITORY + '/releases/download/' + TAG + '/'
    for name, expected in ((FACTORY, admission['factory']), (SD_ARCHIVE, admission['sd_archive']),
                           ('qualification.json', admission['qualification'])):
        row = assets.get(name)
        require(row is not None and row['state'] == 'uploaded' and type(row['id']) is int and row['id'] > 0 and
                row['size'] == expected['bytes'] and row['digest'] == 'sha256:' + expected['sha256'] and
                row['browser_download_url'] == base + name, 'Published asset differs: ' + name)


def fresh_catalog(receipt, rid, commit, admission=None):
    """Verify fresh saved get responses; authenticated collection is external.

    Required envelope: observed_at, source="catalog", release (the catalog get
    response), payload_plan (the payload_plan get response), and
    raw_response_sha256 = SHA256(canonical({release, payload_plan})). Strip the
    unrelated flash_inbox field before saving. Never substitute hand-entered
    revisions for these exact responses. The CLI cannot authenticate the tool
    session; independent collection/review remains an explicit trust boundary.
    """
    at = datetime.fromisoformat(receipt['observed_at'].replace('Z', '+00:00'))
    require(at.tzinfo is not None and 0 <= (datetime.now(timezone.utc) - at).total_seconds() <= 300,
            'Fresh current catalog readback required (within five minutes)')
    require(receipt.get('source') == 'catalog', 'Catalog source required')
    release, plan = receipt['release'], receipt['payload_plan']
    require(receipt['raw_response_sha256'] == sha(canonical({'release': release, 'payload_plan': plan})),
            'Catalog response digest differs')
    cid = REPOSITORY.split('/', 1)[1] + ':' + TAG
    data = release['data']
    require(release['kind'] == 'release' and release['id'] == cid and release['archived'] is False and
            data['repo'] == REPOSITORY.split('/', 1)[1] and data['tag'] == TAG and
            data['source_commit'] == commit and data['hardware_profiles'] == ['x4'], 'Current catalog identity differs')
    revision = release['revision']
    require(type(revision) is int and revision > 0 and type(plan['release_revision']) is int and
            plan['release_revision'] == revision and type(plan['catalog_revision']) is int and
            plan['catalog_revision'] == revision and type(plan['revision']) is int and plan['revision'] >= 0,
            'Current catalog revisions required')
    require(plan['payload_manifest'] is None and plan['context'] is None,
            'Existing payload association requires separate explicit review')
    if admission is not None:
        assets = data['assets']
        require(len({row['name'] for row in assets}) == len(assets), 'Ambiguous catalog asset identity')
        indexed = {row['name']: row for row in assets}
        base = 'https://github.com/' + REPOSITORY + '/releases/download/' + TAG + '/'
        for name, expected in ((FACTORY, admission['factory']), (SD_ARCHIVE, admission['sd_archive']),
                               ('qualification.json', admission['qualification'])):
            row = indexed.get(name)
            require(row is not None and row['size'] == expected['bytes'] and
                    row['digest'] == 'sha256:' + expected['sha256'] and row['url'] == base + name,
                    'Catalog asset differs: ' + name)
        require(data['flash'] == {'profile': 'x4', 'asset_name': FACTORY, 'offset': 0, 'size': 16777216},
                'Catalog factory selection differs')
    return {'id': cid, 'revision': revision, 'repository': REPOSITORY, 'release_id': rid, 'tag': TAG, 'source_commit': commit}


def check_installed(evidence, contract):
    require(evidence.get('firmware_id') == BOOTSTRAP and evidence.get('confirmed_installed') is True,
            'Confirmed installed .123 bootstrap evidence required')
    require(evidence.get('factory_sha256') == contract['baseline']['factory']['sha256'], 'Installed bootstrap factory identity differs')
    require(evidence.get('product_id') == 'xteink-x4-pro' and evidence.get('source') in ('user-confirmation', 'verified-device-readback'),
            'Explicit installation evidence source required')
    require(isinstance(evidence.get('evidence_reference'), str) and evidence['evidence_reference'].strip() and
            isinstance(evidence.get('confirmed_at'), str), 'Traceable installation evidence required')
    at = datetime.fromisoformat(evidence['confirmed_at'].replace('Z', '+00:00'))
    require(at.tzinfo is not None and at <= datetime.now(timezone.utc), 'Invalid installation confirmation time')


def manifest_for(v, files, factory, identity, product, evidence, operation, fixture, candidate=False, operation_plan=None):
    require(operation in ('create', 'replace', 'selected'), 'Select explicit create or replace for every required path')
    if operation == 'selected':
        require(isinstance(operation_plan, dict) and set(operation_plan) == set(files),
                'Selected operation plan must name every exact required path, and no others')
        require(all(value in ('create', 'replace') for value in operation_plan.values()), 'Unsupported selected file operation')
    else:
        require(operation_plan is None, 'Do not combine uniform operation with selected plan')
        operation_plan = {name: operation for name in files}
    baseline = fixture and not candidate
    firmware_id = 'fixture-x4-0123-baseline' if baseline else TAG
    entries, contents, directories = [], {'firmware/' + FACTORY: factory}, set()
    for index, (name, data) in enumerate(sorted(files.items(), key=lambda row: row[0].encode())):
        checked_destination(name)
        source = 'payload/file-%04d.bin' % index
        entries.append({'volume': VOLUME, 'destination': '/' + name, 'source': source, 'operation': operation_plan[name],
                        'owner': OWNER, 'previous': None, **record(data)})
        contents[source] = data
        directories.update(v.parent_paths('/' + name))
    binding = {'firmware_id': firmware_id, 'volume': VOLUME, 'namespace_id': '12', 'evidence': evidence}
    consumer = {'id': OWNER, 'firmware_id': firmware_id, 'evidence': evidence}
    install = {'method_id': 'esptool-full-0x0', 'kind': 'factory', 'artifact_ids': ['factory-image'],
               'settings_effect': 'erased', 'erase_disclosure': 'Full factory flash at offset 0 erases internal saved settings and data. Back up first. Install and verify every required external file after flash; SD survival is not assumed. Unrelated files are preserved. No rollback or atomic replacement is provided.',
               'volume_effects': [{'volume': VOLUME, 'effect': 'unknown', 'evidence': evidence}], 'evidence': evidence}
    operations = sorted({'stat', 'get'} | set(operation_plan.values()) | ({'mkdir'} if directories else set()))
    payload = {'id': 'x4-baseline-fixture' if baseline else 'x4-external-content-' + VERSION, 'owner': OWNER,
               'volumes': [{'id': VOLUME, 'consumer': consumer, 'requirements': {'case_semantics': 'ascii-insensitive',
                   'hierarchical': bool(directories), 'operations': operations, 'path_encoding': 'utf-8-exact'}}],
               'bindings': [binding], 'directories': [{'volume': VOLUME, 'path': name, 'operation': 'ensure-directory'}
                   for name in sorted(directories, key=lambda name: (name.count('/'), name.encode()))],
               'files': entries, 'totals': {'file_count': len(entries), 'bytes': sum(len(b) for b in files.values())}}
    payload['inventory_sha256'] = v.inventory_hash(payload)
    manifest = {'schema_version': '1.0.0', 'container_format': 'risc-catalog-payload-zip-store-v1', 'fixture': fixture,
                'description': ('SYNTHETIC NON-INSTALLABLE .123 baseline fixture. Not a qualified .124 release.' if baseline else
                    'NONINSTALLABLE actual .124 candidate bytes with synthetic release/catalog identity; installed bootstrap and hardware revision are not established.' if fixture else
                    'X4 .124 qualified factory and complete external payload. Software qualification only; device acceptance remains pending.'),
                'catalog_release': identity, 'product': product,
                'firmware': {'id': firmware_id, 'version': '0.1.123-baseline-fixture' if baseline else VERSION,
                    'source_commit': identity['source_commit'], 'artifacts': [{'id': 'factory-image', 'source': 'firmware/' + FACTORY,
                        **record(factory)}], 'install': install},
                'payload': payload, 'plan': {'purpose': 'bootstrap' if baseline else 'combined-update',
                    'order': ['firmware', 'payload', 'verify'], 'pre_firmware_id': None if baseline else BOOTSTRAP, 'policy': POLICY.copy()}}
    return manifest, contents


def fixture_context(v, manifest, raw):
    require(manifest['fixture'] is True, 'Only fixture trust may be generated here')
    p = manifest['payload']; product = manifest['product']; fw = manifest['firmware']
    return {'context_version': '1.0.0', 'fixture': True, 'product_id': product['id'],
            'hardware_profile': product['hardware_profiles'][0], 'hardware_revision': product['hardware_revisions'][0],
            'installed_firmware_id': manifest['plan']['pre_firmware_id'], 'supported_methods': ['esptool-full-0x0'],
            'trusted_manifest_sha256': sha(v.canonical(manifest)), 'trusted_container_sha256': sha(raw),
            'trusted_binding_sha256': [sha(v.canonical(b)) for b in p['bindings']],
            'trusted_consumer_sha256': [sha(v.canonical(p['volumes'][0]['consumer']))],
            'trusted_install_sha256': sha(v.canonical(fw['install'])),
            'limits': {'container_bytes': len(raw), 'inventory_files': len(p['files'])},
            'namespaces': [{'firmware_id': fw['id'], 'namespace_id': '12', 'writable': True, 'hierarchical': True,
                'case_semantics': 'ascii-insensitive', 'operations': ['stat', 'get', 'mkdir', 'create', 'replace'],
                'max_component_bytes': 127, 'max_path_bytes': 511, 'max_file_bytes': max(f['bytes'] for f in p['files']),
                'write_budget_bytes': p['totals']['bytes'], 'forbid_trailing_dot_space': True, 'forbidden_characters': ':\\*?"<>|'}]}


def build(*, schema, factory, sd_archive, output, operation, mode='prepare', admission=None, qualification=None,
          release_record=None, catalog_record=None, installed_bootstrap=None, trusted_context=None, operation_plan=None):
    require(mode in ('prepare', 'prepare-candidate', 'finalize'), 'Unknown preparation mode')
    output = Path(output)
    require(not output.exists(), 'Output directory must be new')
    v = schema_module(schema)
    factory_raw = regular_bytes(factory, 16 * 1024 * 1024)
    archive, files = read_payload(sd_archive)
    contract = load_json(CONTRACT)
    fixture = mode != 'finalize'
    if mode == 'prepare':
        check_baseline(factory_raw, archive, files)
        identity = {'id': 'fixture-x4-baseline-not-installable', 'revision': 1, 'repository': REPOSITORY,
                    'release_id': '1', 'tag': 'fixture-x4-0123-baseline', 'source_commit': contract['baseline']['source_commit']}
        product = {'id': 'xteink-x4-pro', 'hardware_profiles': ['x4'], 'hardware_revisions': ['fixture-unspecified'],
                   'storage_abi': 'RiscStorageFilesV1', 'wire_protocol': 'RTEF1', 'serial_contract_version': '1.0.0'}
        evidence = {'url': contract['baseline']['release_evidence_url'], 'sha256': contract['baseline']['release_evidence_sha256']}
    elif mode == 'prepare-candidate':
        require(admission is not None and qualification is not None, 'Candidate preparation requires exact admission and qualification')
        a = load_json(admission); qraw = regular_bytes(qualification, 8 * 1024 * 1024); q = parse(qraw)
        check_qualification(a, q, qraw, factory_raw, archive, files, require_hardware_revision=False)
        identity = {'id': 'fixture-x4-0124-candidate-not-installable', 'revision': 1, 'repository': REPOSITORY,
                    'release_id': '1', 'tag': TAG, 'source_commit': a['source_commit']}
        product = {'id': a['product_id'], 'hardware_profiles': [a['hardware_profile']], 'hardware_revisions': ['fixture-unspecified'],
                   'storage_abi': 'RiscStorageFilesV1', 'wire_protocol': 'RTEF1', 'serial_contract_version': '1.0.0'}
        # Not a claim that this asset already exists: all evidence is explicitly fixture-only.
        evidence = {'url': 'https://github.com/' + REPOSITORY + '/releases/download/' + TAG + '/qualification.json', 'sha256': sha(qraw)}
    else:
        require(all(p is not None for p in (admission, qualification, release_record, catalog_record, installed_bootstrap, trusted_context)),
                'Finalization requires qualification, real release metadata, current catalog, installation evidence and independent context')
        a = load_json(admission); qraw = regular_bytes(qualification, 8 * 1024 * 1024); q = parse(qraw)
        check_qualification(a, q, qraw, factory_raw, archive, files)
        metadata = load_json(release_record); rid = release_identity(metadata, a)
        verify_public_assets(metadata, a)
        live_release(metadata)
        identity = fresh_catalog(load_json(catalog_record), rid, a['source_commit'], a)
        check_installed(load_json(installed_bootstrap), contract)
        product = {'id': a['product_id'], 'hardware_profiles': [a['hardware_profile']], 'hardware_revisions': [a['hardware_revision']],
                   'storage_abi': 'RiscStorageFilesV1', 'wire_protocol': 'RTEF1', 'serial_contract_version': '1.0.0'}
        evidence = {'url': 'https://github.com/' + REPOSITORY + '/releases/download/' + TAG + '/qualification.json', 'sha256': sha(qraw)}
    selected = load_json(operation_plan) if operation_plan is not None else None
    manifest, contents = manifest_for(v, files, factory_raw, identity, product, evidence, operation, fixture,
                                      candidate=mode == 'prepare-candidate', operation_plan=selected)
    raw = v.pack(manifest, contents)
    require(raw == v.pack(manifest, dict(reversed(list(contents.items())))), 'Canonical pack depends on input order')
    context = fixture_context(v, manifest, raw) if fixture else load_json(trusted_context)
    if not fixture:
        require(context['fixture'] is False and context['installed_firmware_id'] == BOOTSTRAP, 'Independent nonfixture context required')
        require(len(context['namespaces']) == 1 and context['namespaces'][0]['namespace_id'] == '12' and
                context['namespaces'][0]['firmware_id'] == TAG, 'Only qualified external namespace12 is admitted')
    v.validate_manifest(manifest, context, allow_fixture=fixture)
    stem = ('X4-baseline-NONINSTALLABLE-fixture-' if mode == 'prepare' else
            'X4-' + VERSION + '-NONINSTALLABLE-candidate-fixture-' if fixture else 'X4-' + VERSION + '-paired-') + operation
    manifest_name, zip_name = stem + '.json', stem + '.zip'
    descriptor = {'schema_version': '1.0.0', 'manifest': {'asset_name': manifest_name, **record(v.canonical(manifest))},
                  'container': {'asset_name': zip_name, **record(raw)}}
    v.schema_check(descriptor, 'descriptor.schema.json')
    output.mkdir(parents=True)
    (output / manifest_name).write_bytes(v.canonical(manifest)); (output / zip_name).write_bytes(raw)
    (output / 'context.json').write_bytes(v.canonical(context))
    result = v.validate_container(output / zip_name, context, allow_fixture=fixture)
    # Never emit the normal descriptor filename for a fixture.
    (output / ('NONINSTALLABLE-fixture-descriptor.json' if fixture else 'descriptor.json')).write_bytes(v.canonical(descriptor))
    report = {'schema': 1, 'mode': mode, 'fixture': fixture, 'synthetic_release_identity': fixture,
              'baseline_only_not_124': mode == 'prepare', 'candidate_fixture_not_release': mode == 'prepare-candidate', 'publication_authorized': False, 'catalog_associated': False,
              'hardware_tested': False, 'device_accessed': False, 'frozen_schema_revision': SCHEMA_REVISION,
              'input_factory': record(factory_raw), 'input_sd_archive': record(archive),
              'payload_files': {name: record(data) for name, data in sorted(files.items())},
              'provider': {'id': 'x4pro-sd', 'instance': 9, 'wire_namespace': 12, 'volume': VOLUME},
              'operation': operation, 'operation_plan_sha256': sha(canonical(selected)) if selected is not None else None,
              'automatic_operation_selection': False, 'result': result,
              'limits': ['Static preflight is not live provider admission, free-space proof or device acceptance.',
                         'Catalog readback receipt authenticity requires independent operator review.',
                         'Publication, exact public asset readback and catalog association remain separate gates.']}
    (output / 'preparation-report.json').write_bytes(canonical(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'prepare-candidate', 'finalize'))
    for name in ('schema', 'factory', 'sd-archive', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--operation', choices=('create', 'replace', 'selected'), required=True)
    for name in ('admission', 'qualification', 'release-record', 'catalog-record', 'installed-bootstrap', 'trusted-context', 'operation-plan'):
        parser.add_argument('--' + name, type=Path)
    try:
        result = build(**vars(parser.parse_args()))
        print(json.dumps({k: result[k] for k in ('mode', 'fixture', 'publication_authorized', 'result')}, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        print('REJECT: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
