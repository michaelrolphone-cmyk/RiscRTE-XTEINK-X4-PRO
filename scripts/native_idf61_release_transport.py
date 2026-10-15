#!/usr/bin/env python3
"""Stage unchanged X4 native artifacts from hash-pinned official Runtime evidence.

This is release transport, not a build, qualification receipt issuer or flasher.
The guarded publication manifest is deliberately absent until qualification.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
import transport_native_idf61_release as outer

PRODUCT = 'x4'
VERSION = '0.1.122'
RUNTIME_REPOSITORY = 'michaelrolphone-cmyk/RiscRTE'
RUNTIME_TAG = 'firmware-v0.4.0'
EVIDENCE_ASSET = 'Runtime-0.4.0-X4-0.1.122-Native-IDF61-Evidence.zip'
SD_ASSET = 'X4-0.1.121-Complete-SD-Keep-Existing.zip'
ASSETS = {'factory-candidate-erases-data-0x0.bin', 'firmware.bin', 'bootloader.bin',
          'partitions.bin', 'store.bin', SD_ASSET}
TRACES = ('app_deps', 'app_inputs', 'app_commands', 'bootloader_deps', 'bootloader_inputs', 'bootloader_commands', 'app_phony_queries', 'bootloader_phony_queries')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def checksums(raw):
    rows = {}
    for line in raw.decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
        require(match is not None and match[2] not in rows, 'Invalid/duplicate candidate checksum')
        rows[match[2]] = match[1]
    return rows


def archive_members(raw):
    result = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.infolist()) < 20000, 'Excessive evidence archive members')
        require(sum(row.file_size for row in archive.infolist()) <= 2 * 1024**3, 'Excessive uncompressed evidence')
        for row in archive.infolist():
            path = PurePosixPath(row.filename)
            require(not path.is_absolute() and '..' not in path.parts and '\\' not in row.filename and
                    str(path) == row.filename.rstrip('/') and path.parts[0] in ('candidate', 'build', 'metadata', 'logs'),
                    'Unsafe/noncanonical evidence path: ' + row.filename)
            require(not stat.S_ISLNK(row.external_attr >> 16), 'Evidence symlink rejected')
            if row.is_dir():
                continue
            require(row.filename not in result, 'Duplicate evidence path')
            result[row.filename] = archive.read(row)
    return result


def verify_candidate(files, manifest, contract):
    """Recheck delivered byte custody; never claim a fresh build from JSON alone."""
    get = lambda name: files['candidate/' + name]
    report = outer.decode(get('qualification.json'))
    lock_bytes = get('source-lock.json')
    lock = outer.decode(lock_bytes)
    require(report['status'] == 'software-qualified-candidate-hardware-pending', 'Candidate qualification status differs')
    for name, value in dict(publication_enabled=False, hardware_tested=False, device_accessed=False,
                            version_reserved_by_recipe=False, factory_erases_data=True, preserving_update_kit_emitted=False,
                            preserving_sdk_migration_eligible=False, sd_unchanged=True,
                            device_msc_sd_workflow_preserved=True).items():
        require(report.get(name) is value, 'Candidate safety/workflow flag differs: ' + name)
    require(lock.get('publication_enabled') is False and lock['candidate_version'] == VERSION,
            'Wrong candidate version or publication policy')
    require(report['input_lock'] == lock and report['input_lock_sha256'] == digest(lock_bytes)['sha256'], 'Source-lock disagreement')
    require(lock['sources']['product']['revision'] == manifest['product_source'] and
            lock['sources']['runtime']['revision'] == manifest['runtime_source'], 'Qualified source identities differ')
    require(lock['baseline_contract_sha256'] == digest(encoded(contract))['sha256'], 'Baseline contract differs')
    require(report['baseline_contract'] == contract and contract['product'] == 'x4', 'Reported released baseline differs')
    require(report['unchanged_store_payloads'] == contract['store_file_count'] - 1 == 106, 'Retained internal payload inventory differs')
    for key in ('arduino_core_linked', 'ordinary_app_payloads_rebuilt', 'unselected_usb_host_controller', 'file_source_enabled'):
        require(report['native'][key] is False, 'Native composition limit differs: ' + key)
    require(report['native']['elf_bin_identical'] is True, 'Native ELF/BIN equality missing')
    require(set(report['artifacts']) == ASSETS, 'Unexpected/missing candidate assets')
    candidates = {name[len('candidate/'):] for name in files if name.startswith('candidate/')}
    require(candidates == ASSETS | {'qualification.json', 'source-lock.json', 'SHA256SUMS'}, 'Unexpected candidate output (including preserving kits)')
    for name, row in report['artifacts'].items():
        require(digest(get(name)) == row, 'Qualified candidate payload differs: ' + name)
    sums = checksums(get('SHA256SUMS'))
    require(set(sums) == candidates - {'SHA256SUMS'}, 'Incomplete candidate checksum manifest')
    require(all(digest(get(name))['sha256'] == value for name, value in sums.items()), 'Candidate checksum mismatch')
    require(digest(get(SD_ASSET)) == {key: contract['sd'][key] for key in ('bytes', 'sha256')}, 'Released SD bytes changed')
    native_files = lock['native_files']
    required_native = {'firmware_elf', 'firmware_bin', 'firmware_map', 'bootloader_elf', 'bootloader', 'partitions',
                       'compile_commands', 'bootloader_compile_commands', 'sdkconfig', 'sdkconfig_json', 'sdkconfig_header',
                       'bootloader_sdkconfig', 'bootloader_sdkconfig_header', 'project_description', 'flasher_args', 'x4_selection'}
    require(required_native <= native_files.keys(), 'Incomplete locked native evidence')
    for key, row in native_files.items():
        path = PurePosixPath(row['path'])
        require(not path.is_absolute() and '..' not in path.parts and str(path) == row['path'], 'Unsafe locked native artifact path')
        require(digest(files['build/' + str(path)]) == {name: row[name] for name in ('bytes', 'sha256')}, 'Native evidence differs: ' + key)
    for asset, key in (('firmware.bin', 'firmware_bin'), ('bootloader.bin', 'bootloader'), ('partitions.bin', 'partitions')):
        require(get(asset) == files['build/' + native_files[key]['path']], 'Delivered native payload differs from linked evidence')
    factory = get('factory-candidate-erases-data-0x0.bin')
    require(len(factory) == 0x1000000 and len(get('store.bin')) == 0x510000 and
            factory[0x10000:0x10000 + len(get('firmware.bin'))] == get('firmware.bin') and
            factory[0x2f0000:0x800000] == get('store.bin') and
            factory[:len(get('bootloader.bin'))] == get('bootloader.bin') and
            factory[0x8000:0x8000 + len(get('partitions.bin'))] == get('partitions.bin'), 'Factory component custody differs')
    native_elf_hash = native_files['firmware_elf']['sha256']
    for key in ('x4_startup', 'x4_bootlog_memory', 'radio_iq'):
        require(report['native'][key]['elf_sha256'] == native_elf_hash, 'Native proof is bound to another ELF: ' + key)
    memory = report['native']['x4_bootlog_memory']
    require(memory['input_kind'] == 'final-elf' and memory['copied_bytes_external'] == 4528 and
            memory['rtc_record_bytes'] == 264 and len(memory['internal_controls']) == 12 and
            memory['hardware_qualified'] is False, 'Incomplete X4 bootlog placement proof')
    startup = report['native']['x4_startup']
    require(len(startup['bypass_mutations_rejected']) == 5 and startup['hardware_qualified'] is False, 'Incomplete X4 startup proof')
    require(report['native']['radio_iq']['target_identity'] == contract['target'], 'Wrong IQ target proof')
    for key, count, sanitized in (('admission', 43, False), ('admission_sanitized', 43, True),
                                  ('sd_admission', 49, False), ('sd_admission_sanitized', 49, True)):
        result = report[key]
        require(result['elf_count'] == count and result['native_elf_sha256'] == native_elf_hash and
                result['sanitized'] is sanitized and result['target_instructions_executed'] is False,
                'Incomplete native-bound admission: ' + key)
        if key.startswith('sd_'):
            require(result['device_msc_provider_retained'] is True and len(result['results']) == 49, 'Incomplete SD provider coverage')
            rows = {row['path']: row for row in result['results']}
            require(set(rows) == set(contract['sd']['elf_imports']), 'Incomplete/duplicate SD ELF proof paths')
            for path, row in rows.items():
                require(row['sha256'] == contract['sd']['files'][path]['sha256'] and
                        row['role'] == contract['sd']['files'][path]['role'] and
                        row['imports'] == contract['sd']['elf_imports'][path] and
                        set(row['compiled_public_exports']) == set(row['imports']), 'SD proof inventory differs')
                require(all(row[name] is True for name in ('strict_admission', 'wrong_role_rejected', 'unsafe_operation_rejected', 'each_missing_import_rejected')), 'Incomplete SD negative controls')
        else:
            require(result['prepared'] is True and result['cohort_validated'] is True and result['hardware_calls'] == result['storage_calls'] == 0, 'Production cohort admission failed')
    preservation = report['preservation_software_model']
    require(preservation['cases'] == 496 and preservation['passed'] is True and preservation['nvs_and_appdata_preserved'] is True and preservation['unassigned_gap_and_trailing_flash_preserved'] is True and preservation['hardware_tested'] is False and preservation['bootloader_compatibility_tested'] is False, 'Preservation model or hardware limits differ')
    closure = outer.decode(files['build/native-build-evidence/build-closure.json'])
    require(report['build_closure'] == closure and files['build/native-build-evidence/source-lock.json'] == lock_bytes, 'Build closure/source-lock disagreement')
    require(closure['sources'] == lock['sources'] and closure['fresh_build'] is True and
            closure['same_process_qualification'] is True and closure['compile_jobs'] == 1 and
            closure['detached_receipt_is_attestation'] is False, 'Incomplete controlled build receipt')
    for key, row in native_files.items():
        require(closure['artifacts'][key] == {name: row[name] for name in ('bytes', 'sha256')}, 'Controlled artifact lock differs')
    require(set(closure['traces']) == set(TRACES), 'Incomplete controlled trace inventory')
    for name in TRACES:
        require(digest(files['build/native-build-evidence/' + name + '.txt']) == closure['traces'][name], 'Build trace differs: ' + name)
    return report


def final_contract(contract):
    require(contract.get('schema') == 1 and contract.get('finalized') is True, 'Transport contract is not finalized')
    require(type(contract.get('publication_enabled')) is bool, 'Explicit publication gate required')
    require(contract['product'] == 'x4' and contract['repository'] == 'michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO'
            and contract['version'] == contract['candidate_version'] == VERSION, 'Wrong X4 product/version')
    require(contract['release_tag'] == 'test-native-idf61-' + VERSION and
            contract['release_branch'] == 'work/native-idf-6.1', 'Unreviewed release target')
    require(contract['runtime_repository'] == RUNTIME_REPOSITORY and contract['runtime_tag'] == RUNTIME_TAG and
            contract['evidence_asset'] == EVIDENCE_ASSET, 'Unreviewed Runtime artifact destination')
    require(set(contract['sources']) == outer.ROLES and
            all(outer.hex_value(value, 40) for value in contract['sources'].values()), 'Exact source roles/pins required')
    require(contract['sources']['runtime'] == contract['runtime_revision'] == contract['runtime_release_revision'], 'Runtime release/source mismatch')
    for name in ('runtime_manifest_sha256', 'evidence_sha256', 'qualification_sha256'):
        require(outer.hex_value(contract[name], 64), 'Missing final digest: ' + name)
    for name in ('runtime_run_id', 'runtime_run_attempt', 'runtime_artifact_id'):
        require(type(contract[name]) is int and contract[name] > 0, 'Missing official CI identity: ' + name)
    require(set(contract['candidate_artifacts']) == ASSETS, 'Incomplete candidate payload pins')
    for row in contract['candidate_artifacts'].values():
        require(type(row['bytes']) is int and row['bytes'] > 0 and outer.hex_value(row['sha256'], 64), 'Invalid payload pin')


def stage(contract_path, evidence_path, manifest_path, baseline_path, source_revision, output):
    contract_bytes = contract_path.read_bytes()
    contract = outer.decode(contract_bytes)
    final_contract(contract)
    require(outer.hex_value(source_revision, 40) and not output.exists(), 'Exact transport source and new output required')
    manifest_bytes = manifest_path.read_bytes()
    members, runtime_artifact = outer.verify_runtime_envelope(contract, manifest_bytes, evidence_path)
    raw = evidence_path.read_bytes()
    require(outer.digest(raw) == contract['evidence_sha256'], 'Original evidence changed during validation')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        lock = outer.decode(archive.read('candidate/source-lock.json'))
        wanted = {'candidate/' + name for name in ASSETS | {'qualification.json', 'source-lock.json', 'SHA256SUMS'}}
        wanted.update('build/' + str(outer.safe_name(row['path'])) for row in lock['native_files'].values())
        wanted.update('build/native-build-evidence/' + name for name in
                      ('build-closure.json', 'source-lock.json', *(name + '.txt' for name in TRACES)))
        require({name for name in members if name.startswith('candidate/')} == {name for name in wanted if name.startswith('candidate/')}, 'Unexpected candidate output')
        files = {name: archive.read(name) for name in wanted}
        require(all(digest(value) == members[name] for name, value in files.items()), 'Evidence member changed')
    require(outer.digest(files['candidate/qualification.json']) == contract['qualification_sha256'], 'Qualification digest differs')
    baseline = outer.decode(baseline_path.read_bytes())
    require(encoded(baseline) == baseline_path.read_bytes(), 'Baseline contract must retain its pinned canonical bytes')
    report = verify_candidate(files, {'product_source': contract['sources']['product'],
                                    'runtime_source': contract['sources']['runtime']}, baseline)
    require(report['input_lock']['sources'] == runtime_artifact['sources'], 'Runtime/candidate source locks differ')
    require(report['artifacts'] == contract['candidate_artifacts'], 'Final payload contract differs')
    stem = 'X4-' + VERSION + '-Native-IDF61'
    output_files = {stem + '-factory-erases-data-0x0.bin': files['candidate/factory-candidate-erases-data-0x0.bin'],
                    stem + '-Evidence.zip': raw, SD_ASSET: files['candidate/' + SD_ASSET],
                    'qualification.json': files['candidate/qualification.json'], 'source-lock.json': files['candidate/source-lock.json'],
                    'runtime-release-manifest.json': manifest_bytes, 'transport-contract.json': contract_bytes}
    for name in ('firmware.bin', 'bootloader.bin', 'partitions.bin', 'store.bin'):
        output_files[stem + '-' + name] = files['candidate/' + name]
    output_files['RELEASE-NOTES.txt'] = ("X4 0.1.122 native ESP-IDF 6.1 candidate\n\n"
        "Software-qualified; hardware testing is pending.\n"
        "WARNING: the factory image erases internal saved settings and data.\n"
        "No data-preserving SDK migration or OTA kit is supplied. The separate firmware,\n"
        "bootloader, partitions and store files are evidence, not a flashing procedure.\n"
        "Exact deployed-bootloader boot, health confirmation and rollback remain untested.\n"
        "The original controlled Runtime CI evidence ZIP is copied byte-for-byte.\n"
        "The complete SD ZIP is the unchanged released 0.1.121 package. Merge/replace only\n"
        "matching SD paths; do not format or delete other books, ROMs, saves or settings.\n"
        "The existing user-selected device-MSC SD transfer workflow is retained.\n").encode()
    custody = dict(schema=1, repository=contract['repository'], version=VERSION, candidate_version=VERSION,
                   source_revision=source_revision, compiled_product_revision=contract['sources']['product'],
                   runtime_revision=contract['runtime_revision'], runtime_release_revision=contract['runtime_release_revision'],
                   runtime_tag=RUNTIME_TAG, runtime_run_id=contract['runtime_run_id'],
                   runtime_run_attempt=contract['runtime_run_attempt'], runtime_artifact_id=contract['runtime_artifact_id'],
                   original_evidence_sha256=contract['evidence_sha256'], runtime_manifest_sha256=contract['runtime_manifest_sha256'],
                   qualification_sha256=contract['qualification_sha256'], rebuilt=False, evidence_repacked=False,
                   sd_unchanged=True, device_msc_sd_workflow_preserved=True, limits=outer.LIMITS,
                   artifacts={name: digest(value) for name, value in sorted(output_files.items())})
    output_files['release.json'] = encoded(custody)
    output_files['SHA256SUMS'] = ''.join(outer.digest(value) + '  ' + name + '\n' for name, value in sorted(output_files.items())).encode()
    output.mkdir(parents=True)
    for name, value in output_files.items():
        (output / name).write_bytes(value)
    outer.verify_output(output, outer.digest(output_files['SHA256SUMS']), source_revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('contract', 'evidence', 'runtime-manifest', 'baseline-contract', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    stage(args.contract, args.evidence, args.runtime_manifest, args.baseline_contract, args.source_revision, args.output)


if __name__ == '__main__':
    main()
