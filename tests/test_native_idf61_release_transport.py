#!/usr/bin/env python3
"""Synthetic transport-custody tests; no firmware qualification or publication."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

spec = importlib.util.spec_from_file_location('transport', Path(__file__).resolve().parents[1] / 'scripts/native_idf61_release_transport.py')
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)


def fixture():
    files = {}
    manifest = {'product_source': 'a'*40, 'runtime_source': 'b'*40}
    sd = {'bytes': 2, 'sha256': t.digest(b'sd')['sha256'], 'files': {}, 'elf_imports': {}}
    rows = []
    for n in range(49):
        path = 'Apps/test' + str(n) + '.elf'
        sd['files'][path] = {'sha256': 'c'*64, 'role': 'application'}
        sd['elf_imports'][path] = ['memcpy']
        rows.append(dict(path=path, sha256='c'*64, role='application', imports=['memcpy'],
                         compiled_public_exports={'memcpy': '0x4000'}, strict_admission=True,
                         wrong_role_rejected=True, unsafe_operation_rejected=True, each_missing_import_rejected=True))
    contract = {'product':'x4', 'store_file_count':107, 'target': 'esp32s3-16mb-appdata-iq', 'sd': sd}
    keys = ('firmware_elf', 'firmware_bin', 'firmware_map', 'bootloader_elf', 'bootloader', 'partitions',
            'compile_commands', 'bootloader_compile_commands', 'sdkconfig', 'sdkconfig_json', 'sdkconfig_header',
            'bootloader_sdkconfig', 'bootloader_sdkconfig_header', 'project_description', 'flasher_args', 'x4_selection')
    native = {}
    for key in keys:
        raw = key.encode()
        files['build/' + key] = raw
        native[key] = {'path': key, **t.digest(raw)}
    assets = {'firmware.bin': files['build/firmware_bin'], 'bootloader.bin': files['build/bootloader'],
              'partitions.bin': files['build/partitions'], 'store.bin': bytes(0x510000), t.SD_ASSET: b'sd'}
    factory = bytearray(0x1000000)
    for at, name in ((0, 'bootloader.bin'), (0x8000, 'partitions.bin'), (0x10000, 'firmware.bin'), (0x2f0000, 'store.bin')):
        factory[at:at + len(assets[name])] = assets[name]
    assets['factory-candidate-erases-data-0x0.bin'] = bytes(factory)
    for name, raw in assets.items(): files['candidate/' + name] = raw
    lock = {'publication_enabled': False, 'candidate_version': '0.1.122', 'native_files': native,
            'sources': {role: {'revision': manifest.get(role + '_source', 'c'*40), 'tree': 'd'*40, 'submodules': []} for role in t.outer.ROLES},
            'baseline_contract_sha256': t.digest(t.encoded(contract))['sha256']}
    files['candidate/source-lock.json'] = t.encoded(lock)
    elf_hash = native['firmware_elf']['sha256']
    closure = {'sources': lock['sources'], 'fresh_build': True, 'same_process_qualification': True,
               'compile_jobs': 1, 'detached_receipt_is_attestation': False,
               'artifacts': {key: {n: row[n] for n in ('bytes', 'sha256')} for key, row in native.items()}, 'traces': {}}
    for name in t.TRACES:
        files['build/native-build-evidence/' + name + '.txt'] = b'trace'
        closure['traces'][name] = t.digest(b'trace')
    files['build/native-build-evidence/build-closure.json'] = t.encoded(closure)
    files['build/native-build-evidence/source-lock.json'] = files['candidate/source-lock.json']
    report = dict(status='software-qualified-candidate-hardware-pending', publication_enabled=False,
                  hardware_tested=False, device_accessed=False, version_reserved_by_recipe=False, factory_erases_data=True,
                  preserving_update_kit_emitted=False, preserving_sdk_migration_eligible=False,
                  sd_unchanged=True, device_msc_sd_workflow_preserved=True, input_lock=lock,
                  input_lock_sha256=t.digest(files['candidate/source-lock.json'])['sha256'], baseline_contract=contract,
                  artifacts={name: t.digest(raw) for name, raw in assets.items()}, build_closure=closure, unchanged_store_payloads=106,
                  native={'file_source_enabled':False, 'arduino_core_linked':False, 'ordinary_app_payloads_rebuilt':False, 'unselected_usb_host_controller':False, 'elf_bin_identical':True, 'x4_startup': {'elf_sha256': elf_hash, 'bypass_mutations_rejected': list(range(5)), 'hardware_qualified': False},
                          'x4_bootlog_memory': {'elf_sha256': elf_hash, 'input_kind': 'final-elf', 'copied_bytes_external': 4528,
                                               'rtc_record_bytes': 264, 'internal_controls': dict.fromkeys(range(12), 0), 'hardware_qualified': False},
                          'radio_iq': {'elf_sha256': elf_hash, 'target_identity': contract['target']}},
                  preservation_software_model={'passed':True, 'nvs_and_appdata_preserved':True, 'unassigned_gap_and_trailing_flash_preserved':True, 'cases': 496, 'hardware_tested': False, 'bootloader_compatibility_tested': False})
    for key, count, sanitized in (('admission',43,False),('admission_sanitized',43,True),('sd_admission',49,False),('sd_admission_sanitized',49,True)):
        report[key] = dict(elf_count=count,native_elf_sha256=elf_hash,sanitized=sanitized,target_instructions_executed=False,
                           prepared=True,cohort_validated=True,hardware_calls=0,storage_calls=0,
                           device_msc_provider_retained=True,results=copy.deepcopy(rows))
    refresh(files, report)
    return files, manifest, contract, report


def refresh(files, report):
    files['candidate/qualification.json'] = t.encoded(report)
    files['candidate/SHA256SUMS'] = ''.join(t.digest(raw)['sha256'] + '  ' + path[10:] + '\n'
        for path, raw in sorted(files.items()) if path.startswith('candidate/') and path != 'candidate/SHA256SUMS').encode()


class TransportControls(unittest.TestCase):
    def test_inactive_contract_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not finalized'):
            t.final_contract({'schema': 1, 'finalized': False, 'publication_enabled': False})

    def test_original_zip_and_sd_are_staged_without_repacking(self):
        files, short, baseline, report = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'evidence.zip'
            files['metadata/workflow.yml'] = b'workflow'
            ci = {'GITHUB_REPOSITORY': t.RUNTIME_REPOSITORY, 'GITHUB_SHA': short['runtime_source'],
                  'GITHUB_REF': 'refs/heads/work/native-idf-6.1', 'GITHUB_RUN_ID': '4', 'GITHUB_RUN_ATTEMPT': '1',
                  'GITHUB_WORKFLOW_REF': t.RUNTIME_REPOSITORY + '/.github/workflows/native-idf6.yml@refs/heads/work/native-idf-6.1',
                  'GITHUB_WORKFLOW_SHA': short['runtime_source'], 'PRODUCT': 'x4'}
            files['metadata/ci-run.json'] = t.encoded(ci)
            source_record={'schema':1,'sources':{role:{**row,'clean':True} for role,row in report['input_lock']['sources'].items()}}
            files['metadata/sources-before.json']=files['metadata/sources-after.json']=t.encoded(source_record)
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as writer:
                for name, raw in files.items(): writer.writestr(name, raw)
            members = t.outer.archive_members(archive)
            evidence_hash = t.outer.digest(archive.read_bytes())
            artifact = dict(id=2, name='native-idf6-x4-' + short['runtime_source'], bytes=archive.stat().st_size,
                            sha256=evidence_hash, job_id=3, job_name='native (x4)', sources=report['input_lock']['sources'], members=members)
            runtime = dict(schema=1, enabled=True, repository=t.RUNTIME_REPOSITORY, version='0.4.0', tag=t.RUNTIME_TAG,
                           publication_branch='work/native-idf-6.1', source_sha=short['runtime_source'],
                           source_workflow_sha256=t.outer.digest(b'workflow'), run_id=4, run_attempt=1, workflow_id=5,
                           artifacts={name: artifact for name in ('generic','twatch','waveshare','x4')})
            runtime_bytes=t.encoded(runtime)
            contract=dict(schema=1, finalized=True, publication_enabled=False, product='x4',
                          repository='michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO', version=t.VERSION, candidate_version=t.VERSION,
                          release_tag='test-native-idf61-' + t.VERSION, release_branch='work/native-idf-6.1',
                          runtime_repository=t.RUNTIME_REPOSITORY, runtime_tag=t.RUNTIME_TAG,
                          runtime_revision=short['runtime_source'], runtime_release_revision=short['runtime_source'],
                          evidence_asset=t.EVIDENCE_ASSET, evidence_sha256=evidence_hash,
                          runtime_manifest_sha256=t.outer.digest(runtime_bytes),
                          qualification_sha256=t.outer.digest(files['candidate/qualification.json']),
                          runtime_run_id=4,runtime_run_attempt=1,runtime_artifact_id=2,
                          sources={role: row['revision'] for role,row in report['input_lock']['sources'].items()},
                          candidate_artifacts=report['artifacts'])
            (root/'contract.json').write_bytes(t.encoded(contract))
            (root/'runtime.json').write_bytes(runtime_bytes)
            (root/'baseline.json').write_bytes(t.encoded(baseline))
            output=root/'output'
            t.stage(root/'contract.json', archive, root/'runtime.json', root/'baseline.json', 'f'*40, output)
            self.assertEqual((output/'X4-0.1.122-Native-IDF61-Evidence.zip').read_bytes(), archive.read_bytes())
            self.assertEqual((output/t.SD_ASSET).read_bytes(), files['candidate/' + t.SD_ASSET])
            self.assertFalse(any('preserving' in path.name.lower() for path in output.iterdir()))
            notes=(output/'RELEASE-NOTES.txt').read_text()
            self.assertIn('erases internal saved settings',notes)
            self.assertIn('hardware testing is pending',notes)

    def test_complete_source_bound_transport_fixture(self):
        files, manifest, contract, report = fixture()
        actual = t.verify_candidate(files, manifest, contract)
        self.assertEqual(actual['status'], report['status'])

    def test_hardware_preservation_and_workflow_flags_fail_closed(self):
        files, manifest, contract, report = fixture()
        for name in ('hardware_tested','device_accessed','preserving_update_kit_emitted','preserving_sdk_migration_eligible','sd_unchanged','device_msc_sd_workflow_preserved'):
            changed = copy.deepcopy(report); changed[name] = not changed[name]; refresh(files, changed)
            with self.subTest(flag=name), self.assertRaises(ValueError): t.verify_candidate(files, manifest, contract)

    def test_incomplete_native_bound_admissions_rejected(self):
        files, manifest, contract, report = fixture()
        for key in ('admission','admission_sanitized','sd_admission','sd_admission_sanitized'):
            for field, value in (('elf_count',1),('native_elf_sha256','0'*64),('target_instructions_executed',True)):
                changed = copy.deepcopy(report); changed[key][field] = value; refresh(files, changed)
                with self.subTest(key=key,field=field), self.assertRaises(ValueError): t.verify_candidate(files, manifest, contract)

    def test_sd_negative_control_omission_or_duplicate_rejected(self):
        files, manifest, contract, report = fixture()
        for mode in ('duplicate', 'negative'):
            changed = copy.deepcopy(report)
            if mode == 'duplicate': changed['sd_admission']['results'][1] = changed['sd_admission']['results'][0]
            else: changed['sd_admission']['results'][0]['each_missing_import_rejected'] = False
            refresh(files, changed)
            with self.subTest(mode=mode), self.assertRaises(ValueError): t.verify_candidate(files, manifest, contract)

    def test_wrong_source_and_mutated_native_evidence_rejected(self):
        files, manifest, contract, report = fixture()
        with self.assertRaises(ValueError): t.verify_candidate(files, {**manifest, 'product_source': 'd'*40}, contract)
        files['build/firmware_elf'] += b'changed'
        with self.assertRaises(ValueError): t.verify_candidate(files, manifest, contract)

    def test_additional_preserving_asset_rejected(self):
        files, manifest, contract, report = fixture()
        files['candidate/preserving-update.zip'] = b'unsafe'; refresh(files, report)
        with self.assertRaises(ValueError): t.verify_candidate(files, manifest, contract)

    def test_incomplete_placement_or_gpio_proof_rejected(self):
        files, manifest, contract, report = fixture()
        for key, field, value in (('x4_bootlog_memory','copied_bytes_external',4520),('x4_bootlog_memory','input_kind','target-object'),('x4_startup','bypass_mutations_rejected',[]),('radio_iq','elf_sha256','f'*64)):
            changed=copy.deepcopy(report); changed['native'][key][field]=value; refresh(files,changed)
            with self.subTest(key=key,field=field), self.assertRaises(ValueError): t.verify_candidate(files,manifest,contract)


    def test_publish_atomically_creates_the_exact_tag_before_release(self):
        text = (Path(__file__).resolve().parents[1] / '.github/workflows/native-idf61-release.yml').read_text()
        self.assertIn('-f "ref=refs/tags/$RELEASE_TAG" -f "sha=$GITHUB_SHA"', text)
        self.assertLess(text.index('gh api --method POST'), text.index('gh release create'))
        self.assertIn("tag['object']['type']=='commit' and tag['object']['sha']==os.environ['GITHUB_SHA']", text)
        self.assertIn('--verify-tag --target "$GITHUB_SHA"', text)


if __name__ == '__main__': unittest.main()
