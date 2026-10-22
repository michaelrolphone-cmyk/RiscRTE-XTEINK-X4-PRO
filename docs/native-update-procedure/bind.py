#!/usr/bin/env python3
"""Offline preparation binding. No device, network, finalization or acceptance mode."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def checked_files(root, entries):
    for path, expected in entries.items():
        require(digest((root / path).read_bytes()) == expected, 'Source changed: ' + path)


def zip_members(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        require(len({r.filename for r in rows}) == len(rows), 'Duplicate ZIP member')
        return {r.filename: archive.read(r) for r in rows if not r.is_dir()}


def check_payload(files, expected):
    require(set(files) == set(expected), 'Payload path set mismatch')
    for path, value in expected.items():
        require(len(files[path]) == value['bytes'], 'Payload length mismatch: ' + path)
        require(digest(files[path]) == value['sha256'], 'Payload hash mismatch: ' + path)


def check_plan(manifest, expected):
    require(manifest.get('fixture') is True, 'Preparation lost fixture boundary')
    require(manifest['plan']['order'] == expected['order'] == ['firmware', 'payload', 'verify'],
            'Unsupported prepared order')
    install = manifest['firmware']['install']
    require(install['method_id'] == expected['flash_method'], 'Flash method mismatch')
    require(install['settings_effect'] == 'erased', 'Settings-erasure disclosure mismatch')
    require(install['volume_effects'] == [{'volume': expected['logical_volume'], 'effect': 'unknown',
                                         'evidence': install['volume_effects'][0]['evidence']}],
            'External flash effect cannot be promoted to preserved')
    require(manifest['payload']['bindings'][0]['namespace_id'] == expected['wire_namespace'] == '12',
            'Wire/provider namespace confusion')
    rows = manifest['payload']['files']
    require(len(rows) == len({r['destination'] for r in rows}) == expected['file_count'] == 78,
            'Manifest file count/uniqueness mismatch')
    inventory = {r['destination'][1:]: {'bytes': r['bytes'], 'sha256': r['sha256']} for r in rows}
    require(all(r['destination'].startswith('/') and r['volume'] == expected['logical_volume'] for r in rows),
            'Manifest destination/volume mismatch')
    require(inventory == {k: {'bytes': v['bytes'], 'sha256': v['sha256']} for k, v in expected['payload_files'].items()}, 'Manifest/admission inventory mismatch')
    require(manifest['payload']['totals'] == {'bytes': expected['payload_bytes'], 'file_count': 78},
            'Payload denominator mismatch')
    require([r['operation'] for r in rows].count('replace') == 77 and
            [r['operation'] for r in rows].count('create') == 1, 'Mixed fixture operation mismatch')


def audit(lock, product, matrix, raw):
    checked_files(product, lock['product']['files'])
    shared = matrix / lock['shared']['directory']
    checked_files(shared, lock['shared']['files'])
    require(len(raw) == lock['artifact']['bytes'] and digest(raw) == lock['artifact']['sha256'],
            'Actions artifact length/hash mismatch')
    members = zip_members(raw)
    for name, expected in lock['artifact']['members'].items():
        require(len(members[name]) == expected['bytes'] and digest(members[name]) == expected['sha256'],
                'Artifact member length/hash mismatch: ' + name)
    candidate = lock['candidate']
    admission = load(members['pair-admission.json'])
    qualification = load(members['qualification.json'])
    require(admission['source_commit'] == candidate['source_commit'] == lock['product']['revision'] and
            admission['ci']['source_commit'] == lock['product']['revision'] and
            admission['ci']['run_id'] == lock['artifact']['run_id'], 'Build/source identity mismatch')
    require(admission['runtime_revision'] == candidate['runtime_revision'], 'Runtime mismatch')
    require(not admission['publication_enabled'] and not admission['hardware_tested'] and
            not qualification['device_accessed'] and not qualification['hardware_tested'] and
            qualification['status'] == 'software-qualified-candidate-hardware-pending',
            'Candidate evidence scope mismatch')
    require(admission['payload_files'] == candidate['payload_files'], 'Admission inventory mismatch')
    require(admission['factory'] == candidate['factory'] and admission['sd_archive'] == candidate['sd_archive'] and
            admission['qualification'] == candidate['qualification'], 'Candidate identity mismatch')
    payload = zip_members(members['X4-0.1.124-Complete-SD-Keep-Existing.zip'])
    check_payload(payload, candidate['payload_files'])
    baseline = load((product / 'docs/native-paired-124/released-baseline.json').read_bytes())['sd']['files']
    require(len(baseline) == 77 and all(candidate['payload_files'].get(k) == v for k, v in baseline.items()),
            'Baseline77 content changed')
    manifest = load(members[candidate['fixture_manifest_member']])
    check_plan(manifest, candidate)
    container = zip_members(members[candidate['fixture_manifest_member'].replace('.json', '.zip')])
    require(load(container['manifest.json']) == manifest, 'Container manifest mismatch')
    for row in manifest['payload']['files']:
        require(container[row['source']] == payload[row['destination'][1:]], 'Container/source payload mismatch')
        require(row['operation'] == ('replace' if row['destination'][1:] in baseline else 'create'),
                'Mixed operation not bound to baseline')
    require(container['firmware/factory-candidate-erases-data-0x0.bin'] ==
            members['factory-candidate-erases-data-0x0.bin'], 'Container factory mismatch')
    expected_members = {'manifest.json', 'firmware/factory-candidate-erases-data-0x0.bin'} | {
        row['source'] for row in manifest['payload']['files']}
    require(set(container) == expected_members, 'Unexpected container member')
    profile = (product / 'profiles/native-paired-124.cmake').read_text()
    serial = (product / 'scripts/native_paired_serial.py').read_text()
    require('RISC_NATIVE_SERIAL_SD_INSTANCE=9' in profile and 'x4pro-sd' in profile and
            "'sd_wire_namespace': 12" in serial and "'sd_provider_instance': 9" in serial,
            'Provider selector/source binding mismatch')
    return load((shared / 'matrix.json').read_bytes()), load((shared / 'result-template.json').read_bytes())


def case_note(case_id):
    if case_id.startswith('file-'):
        return 'Use frozen deterministic fixture bytes only at approved disposable namespace-12 paths; never overwrite candidate files. Capture independent S0/S1.'
    if case_id.startswith('path-') or case_id in {'create-existing', 'replace-shorter', 'replace-empty', 'replace-missing', 'read-missing', 'parent-file'}:
        return 'Reconcile actual X4 provider capabilities/bounds first. Preserve exact path bytes, including spaces; explicit per-file operations only. No automatic not-applicable decision.'
    if case_id.startswith('namespace-'):
        return 'Bind logical application-content to independently admitted wire12, not provider instance9 or a label. Retain all preflight/service variants with zero-mutation evidence.'
    if case_id == 'flash-effects':
        return 'Separate F0/F1 from serial snapshots. Source declares full-0x0 internal settings/data erasure and unknown external-volume effect; actual device effects remain unverified.'
    if case_id == 'restart-persistence':
        return 'Physical S1/S2, restart kind/timing, all78 full readbacks and independently observed settings/user-file sentinels are mandatory for future hardware acceptance.'
    if case_id == 'whole-payload-failure':
        return 'Freeze all78 paths and11006894 uncompressed bytes. Last-file failure, omitted, duplicate and tampered inventories cannot report overall success.'
    if case_id == 'paired-final-usability':
        return 'Firmware→payload→verify only. Physical supported-order, all78 full hashes and consumer coverage after restart; reject transfer-first with unknown effects. Read-only final mapping never permits uploads.'
    return 'Use exact-source reproducible fault injection where device exercise is unsafe/unavailable; retain every variant and original failed/unverified attempt, custody/offset/transcript and S0/S1. No blind retry or invented recovery.'


def draft(lock, matrix, template):
    require(len(matrix['cases']) == 46 and sum(len(c['variants']) for c in matrix['cases']) == 85,
            'Shared coverage changed')
    require([(c['id'], [v['id'] for v in c['variants']]) for c in template['cases']] ==
            [(c['id'], c['variants']) for c in matrix['cases']], 'Template/matrix coverage mismatch')
    result = copy.deepcopy(template)
    expected = lock['candidate']
    result['product'] = 'xteink-x4-pro'
    result['x4_preparation'] = {
        'runnable': False, 'device_action_authorized': False, 'hardware_acceptance': False,
        'scope': 'Unexecuted candidate-bound result schema; actual release/installed/trust fields remain unbound.',
        'source': lock['product']['revision'], 'shared_source': lock['shared']['revision'],
        'artifact_id': lock['artifact']['artifact_id'], 'artifact_sha256': lock['artifact']['sha256'],
        'candidate_expectation': {k: expected[k] for k in ['version', 'runtime_revision', 'factory', 'sd_archive',
            'logical_volume', 'wire_namespace', 'provider', 'provider_instance', 'order', 'flash_method',
            'declared_settings_effect', 'declared_external_volume_effect']},
        'stop_gates': {k: None for k in ['installed_bootstrap_evidence', 'device_observation_timestamp',
            'actual_device_identifier', 'actual_hardware_revision', 'published_release_and_asset_readback',
            'fresh_catalog_release_and_plan', 'reviewed_nonfixture_trust', 'hello_and_namespaces_before',
            'hello_and_namespaces_after', 'actual_provider_bounds', 'supported_recovery',
            'approved_destinations_and_backups', 'nonfixture_manifest_and_container', 'authorized_hardware_run']},
        'scenario_records_required': ['clean-create78', 'baseline77-plus-new1-explicit-plan', 'repeat-present78'],
        'scenario_operation_examples_are_not_live_selection': True,
        'sentinel_stages_required': ['F0', 'F1', 'fresh-post-flash-S0', 'per-interval-S0', 'per-interval-S1', 'post-restart-S2'],
        'sentinel_kinds_required': ['sibling', 'sibling-directory-if-supported', 'known-test-tree',
            'independent-user-file', 'independent-native-setting', 'other-admitted-volume-if-present']}
    for row in result['cases']:
        row['x4_preparation_note'] = case_note(row['id'])
    for path, value in sorted(expected['payload_files'].items()):
        result['file_results'].append({
            'volume': expected['logical_volume'], 'destination': '/' + path, 'operation': None,
            'initial_snapshot': None, 'expected_bytes': value['bytes'], 'expected_sha256': value['sha256'],
            'actual_bytes': None, 'actual_sha256': None, 'commit_acknowledged': None,
            'readback_close_acknowledged': None, 'readback_crc_match': None,
            'after_last_firmware_step': None, 'after_restart': None, 'consumer_usable': None,
            'environment': None, 'status': 'unverified', 'evidence': [],
            'original_attempt_id': None, 'recovery_receipt': None})
    result['final_payload'].update(expected_files=78, expected_bytes=expected['payload_bytes'])
    result['limitations'] = ['Not runnable final device instructions or hardware acceptance.',
        'Prepared fixture manifest identities and context must not populate actual run fields.',
        'Source-bound historical host receipts are not new shared-matrix or physical-device coverage.']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix', required=True, type=Path)
    parser.add_argument('--artifact', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    lock = load((HERE / 'inputs.json').read_bytes())
    matrix, template = audit(lock, PRODUCT, args.matrix, args.artifact.read_bytes())
    generated = encoded(draft(lock, matrix, template))
    if args.check:
        require((HERE / 'draft.json').read_bytes() == generated, 'Draft is stale or mutated')
    else:
        (HERE / 'draft.json').write_bytes(generated)
    print('PREPARATION ONLY: bound46 cases/85 variants and78 files/11006894 bytes; hardware not tested; all execution gates unresolved.')


if __name__ == '__main__':
    main()
