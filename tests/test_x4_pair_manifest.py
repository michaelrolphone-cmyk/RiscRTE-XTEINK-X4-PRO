#!/usr/bin/env python3
"""Offline negative/positive pair-contract tests. No GitHub writes or device I/O.

Run with X4_PAIR_SCHEMA pointing to the four exact frozen Runtime schema files.
Optional X4_PAIR_BASELINE_INPUTS enables the full published 77-file fixture test.
All synthetic nonfixture metadata stays in memory; no installable descriptor is
produced by these tests. Larger temporary outputs live under /tmp.
"""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pair', ROOT / 'scripts/x4_pair_manifest.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
TEST_ROOT = Path('/tmp/x4-pair-manifest-test')
TEST_ROOT.mkdir(parents=True, exist_ok=True)


class PairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = Path(os.environ['X4_PAIR_SCHEMA'])
        cls.v = p.schema_module(cls.schema)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='unit-', dir=TEST_ROOT)
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.files = {'Apps/demo/image-ab/demo.elf': b'elf-demo', 'Apps/demo/image-ab/manifest.json': b'{}',
                      'Drivers/demo/image-cd.elf': b'driver', 'fonts/Noto Sans/OFL.txt': b'font licence'}
        self.identity = {'id': 'fixture-x4-baseline-not-installable', 'revision': 1, 'repository': p.REPOSITORY,
                         'release_id': '1', 'tag': 'fixture-x4-0123-baseline', 'source_commit': 'a' * 40}
        self.product = {'id': 'xteink-x4-pro', 'hardware_profiles': ['x4'], 'hardware_revisions': ['fixture-unspecified'],
                        'storage_abi': 'RiscStorageFilesV1', 'wire_protocol': 'RTEF1', 'serial_contract_version': '1.0.0'}
        self.evidence = {'url': 'https://example.invalid/fixture-not-installable.json', 'sha256': 'b' * 64}
        self.manifest, self.contents = p.manifest_for(self.v, self.files, b'fixture factory', self.identity,
                                                   self.product, self.evidence, 'create', True)
        self.raw = self.v.pack(self.manifest, self.contents)
        self.context = p.fixture_context(self.v, self.manifest, self.raw)

    def zip_input(self, names=None):
        path = self.root / 'input.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, data in (names or self.files).items():
                z.writestr(name, data)
        return path

    def validate(self, manifest=None, context=None, contents=None):
        manifest = manifest if manifest is not None else self.manifest
        context = copy.deepcopy(context if context is not None else self.context)
        contents = contents if contents is not None else self.contents
        context['trusted_manifest_sha256'] = p.sha(self.v.canonical(manifest))
        raw = self.v.pack(manifest, contents)
        context['trusted_container_sha256'] = p.sha(raw)
        context['limits']['container_bytes'] = len(raw)
        path = self.root / 'pair.zip'
        path.write_bytes(raw)
        return self.v.validate_container(path, context, allow_fixture=True)

    def update_inventory(self):
        self.manifest['payload']['inventory_sha256'] = self.v.inventory_hash(self.manifest['payload'])

    def test_exact_frozen_schema(self):
        self.assertEqual(p.SCHEMA_REVISION, '908355b0509907c05a6dc47a1ccc8e078d6e23b0')
        self.assertEqual(self.v.sha256((self.schema / 'validate.py').read_bytes()), p.SCHEMA_HASHES['validate.py'])

    def test_tampered_schema_rejected_before_import(self):
        for name in p.SCHEMA_HASHES:
            shutil.copy(self.schema / name, self.root / name)
        (self.root / 'validate.py').write_text('raise RuntimeError("must not execute")')
        with self.assertRaisesRegex(ValueError, 'Frozen schema differs'):
            p.schema_module(self.root)

    def test_fixture_full_schema_and_canonical_container(self):
        self.assertEqual(self.validate()['file_count'], 4)
        self.assertEqual(self.raw, self.v.pack(self.manifest, dict(reversed(list(self.contents.items())))))
        self.assertEqual(self.manifest['catalog_release']['release_id'], '1')

    def test_fixture_rejected_by_installable_validator(self):
        with self.assertRaisesRegex(ValueError, 'fixture is not installable'):
            self.v.validate_manifest(self.manifest, self.context)

    def test_trust_generation_refuses_nonfixture(self):
        self.manifest['fixture'] = False
        with self.assertRaisesRegex(ValueError, 'Only fixture trust'):
            p.fixture_context(self.v, self.manifest, self.raw)

    def test_source_names_portable_destination_spaces_retained(self):
        row = next(r for r in self.manifest['payload']['files'] if r['destination'].startswith('/fonts/'))
        self.assertEqual(row['destination'], '/fonts/Noto Sans/OFL.txt')
        self.assertRegex(row['source'], '^payload/file-[0-9]{4}.bin$')
        self.validate()

    def test_directory_order_depth_before_lexicographic(self):
        rows = self.manifest['payload']['directories']
        self.assertEqual(rows, sorted(rows, key=lambda r: (r['volume'], r['path'].count('/'), r['path'].encode())))
        rows.reverse(); self.update_inventory()
        with self.assertRaisesRegex(ValueError, 'noncanonical order: directories'):
            self.validate()

    def test_file_order_is_canonical(self):
        self.manifest['payload']['files'].reverse(); self.update_inventory()
        with self.assertRaisesRegex(ValueError, 'noncanonical order: destinations'):
            self.validate()

    def test_all_files_explicit_create_or_replace(self):
        for operation in ('create', 'replace'):
            m, c = p.manifest_for(self.v, self.files, b'fixture factory', self.identity, self.product, self.evidence, operation, True)
            self.assertEqual({r['operation'] for r in m['payload']['files']}, {operation})
            self.assertTrue(all(r['previous'] is None for r in m['payload']['files']))
            self.validate(m, p.fixture_context(self.v, m, self.v.pack(m, c)), c)
        for operation in ('upsert', 'delete', 'skip', 'directory-replace', 'auto'):
            with self.assertRaisesRegex(ValueError, 'explicit create or replace'):
                p.manifest_for(self.v, self.files, b'factory', self.identity, self.product, self.evidence, operation, True)

    def test_mixed_operations_require_complete_explicit_per_file_plan(self):
        plan = {name: 'replace' for name in self.files}
        plan[next(iter(plan))] = 'create'
        m, contents = p.manifest_for(self.v, self.files, b'factory', self.identity, self.product, self.evidence,
                                     'selected', True, operation_plan=plan)
        self.assertEqual({r['destination'][1:]: r['operation'] for r in m['payload']['files']}, plan)
        self.validate(m, p.fixture_context(self.v, m, self.v.pack(m, contents)), contents)
        for invalid in (None, dict(list(plan.items())[1:]), {**plan, 'Apps/unlisted': 'create'},
                        {**plan, next(iter(plan)): 'skip'}, {**plan, next(iter(plan)): 'auto'}):
            with self.assertRaises(ValueError):
                p.manifest_for(self.v, self.files, b'factory', self.identity, self.product, self.evidence,
                               'selected', True, operation_plan=invalid)
        with self.assertRaisesRegex(ValueError, 'Do not combine'):
            p.manifest_for(self.v, self.files, b'factory', self.identity, self.product, self.evidence,
                           'replace', True, operation_plan=plan)

    def test_unsafe_paths_and_boot_writes_rejected(self):
        for name in ('../x', '/Apps/x', 'Apps//x', 'Apps/../x', 'Apps/x/', 'Apps/x\\y', 'Apps/a:b',
                     'Apps/x\x00z', 'Apps/x.', 'Apps/x ', 'Apps/é', 'Apps/' + 'x' * 128,
                     'boot.json', 'Apps/boot.json', 'Drivers/store.bin', 'firmware.bin', 'Apps/firmware.bin'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                p.checked_destination(name)

    def test_zip_duplicates_rejected(self):
        path = self.zip_input()
        with zipfile.ZipFile(path, 'a') as z:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore'); z.writestr(next(iter(self.files)), b'duplicate')
        with self.assertRaisesRegex(ValueError, 'Duplicate or case'):
            p.read_payload(path)

    def test_case_alias_rejected(self):
        path = self.zip_input({'Apps/demo/file': b'a', 'Apps/DEMO/FILE': b'b'})
        with self.assertRaisesRegex(ValueError, 'case-aliased'):
            p.read_payload(path)

    def test_file_directory_alias_rejected(self):
        path = self.zip_input({'Apps/Demo': b'a', 'Apps/demo/file': b'b'})
        with self.assertRaisesRegex(ValueError, 'File/directory collision'):
            p.read_payload(path)

    def test_symlink_member_rejected(self):
        path = self.root / 'input.zip'
        with zipfile.ZipFile(path, 'w') as z:
            row = zipfile.ZipInfo('Apps/demo/link'); row.create_system = 3
            row.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(row, '/outside')
        with self.assertRaisesRegex(ValueError, 'not a regular file'):
            p.read_payload(path)

    def test_input_symlink_rejected(self):
        path = self.zip_input(); target = self.root / 'link.zip'; target.symlink_to(path)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            p.read_payload(target)

    def test_duplicate_json_member_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            p.parse(b'{"id":1,"id":2}')

    def test_missing_changed_extra_inventory_rejected(self):
        inventory = {name: p.record(data) for name, data in self.files.items()}
        p.checked_inventory(self.files, inventory)
        for changed in ({**self.files, 'Apps/unlisted': b'x'}, dict(list(self.files.items())[1:]),
                        {**self.files, next(iter(self.files)): b'changed'}):
            with self.assertRaises(ValueError): p.checked_inventory(changed, inventory)

    def test_missing_or_extra_container_member_rejected(self):
        for contents in (dict(list(self.contents.items())[1:]), {**self.contents, 'extra.bin': b'x'}):
            with self.assertRaisesRegex(ValueError, 'missing or unlisted'):
                self.validate(contents=contents)

    def test_changed_container_file_rejected(self):
        name = next(k for k in self.contents if k.startswith('payload/'))
        with self.assertRaisesRegex(ValueError, 'file SHA-256 mismatch'):
            self.validate(contents={**self.contents, name: b'xxxxxxxx'})

    def test_unsupported_provider_operation_rejected(self):
        self.context['namespaces'][0]['operations'].remove('create')
        with self.assertRaisesRegex(ValueError, 'unsupported provider operation'):
            self.validate()

    def test_wrong_namespace_rejected(self):
        self.manifest['payload']['bindings'][0]['namespace_id'] = '9'
        self.context['trusted_binding_sha256'] = [p.sha(self.v.canonical(self.manifest['payload']['bindings'][0]))]
        self.update_inventory()
        with self.assertRaisesRegex(ValueError, 'namespace not admitted'):
            self.validate()

    def test_ambiguous_context_namespace_rejected(self):
        self.context['namespaces'].append(copy.deepcopy(self.context['namespaces'][0]))
        with self.assertRaisesRegex(ValueError, 'ambiguous trusted namespace'):
            self.validate()

    def test_insufficient_admitted_write_budget_rejected(self):
        self.context['namespaces'][0]['write_budget_bytes'] = 1
        with self.assertRaisesRegex(ValueError, 'insufficient admitted write budget'):
            self.validate()

    def test_firmware_first_unknown_survival_and_erase_disclosure(self):
        m, _ = p.manifest_for(self.v, self.files, b'factory', self.identity, self.product, self.evidence, 'replace', False)
        self.assertEqual(m['plan']['order'], ['firmware', 'payload', 'verify'])
        self.assertEqual(m['plan']['pre_firmware_id'], p.BOOTSTRAP)
        self.assertEqual(m['firmware']['install']['volume_effects'][0]['effect'], 'unknown')
        self.assertEqual(m['firmware']['install']['settings_effect'], 'erased')
        self.assertEqual(m['plan']['policy']['unrelated_files'], 'preserve')
        self.assertEqual(m['plan']['policy']['on_uncertain_result'], 'stop-inspect-no-automatic-retry')

    def test_payload_first_unknown_survival_rejected(self):
        self.manifest['plan'].update(purpose='combined-update', order=['payload', 'firmware', 'verify'], pre_firmware_id=p.BOOTSTRAP)
        self.context['installed_firmware_id'] = p.BOOTSTRAP
        with self.assertRaisesRegex(ValueError, 'unknown survival'):
            self.validate()

    def test_finalization_missing_prerequisites_has_no_output(self):
        factory = self.root / 'factory.bin'; factory.write_bytes(b'factory')
        with self.assertRaisesRegex(ValueError, 'Finalization requires'):
            p.build(schema=self.schema, factory=factory, sd_archive=self.zip_input(), output=self.root / 'out',
                    operation='create', mode='finalize')
        self.assertFalse((self.root / 'out').exists())

    def test_exact_live_release_record_checked(self):
        m = self.release_metadata()
        self.assertEqual(p.release_identity(m, {'source_commit': 'a' * 40}), '123456')
        for key, value in [('id', 1), ('id', True), ('draft', True), ('tag_name', p.BOOTSTRAP),
                           ('target_commitish', 'main'), ('url', 'https://example.invalid/releases/123456')]:
            changed = {**m, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.release_identity(changed, {'source_commit': 'a' * 40})

    def release_metadata(self):
        return {'id': 123456, 'draft': False, 'prerelease': True, 'published_at': '2026-01-01T00:00:00Z',
                'tag_name': p.TAG, 'target_commitish': 'a' * 40,
                'url': 'https://api.github.com/repos/' + p.REPOSITORY + '/releases/123456',
                'html_url': 'https://github.com/' + p.REPOSITORY + '/releases/tag/' + p.TAG}

    def test_live_release_cannot_use_supplied_alternate_endpoint(self):
        metadata = self.release_metadata()
        response = mock.MagicMock(); response.__enter__.return_value = response
        response.url = metadata['url']; response.read.return_value = p.canonical(metadata)
        with mock.patch.object(p.urllib.request, 'urlopen', return_value=response) as call:
            self.assertEqual(p.live_release(metadata), metadata)
            self.assertEqual(call.call_args.args[0].full_url, metadata['url'])
            response.read.return_value = p.canonical({**metadata, 'draft': True})
            with self.assertRaisesRegex(ValueError, 'stale or differs'):
                p.live_release(metadata)

    def catalog_receipt(self):
        release = {'kind': 'release', 'id': p.REPOSITORY.split('/', 1)[1] + ':' + p.TAG, 'revision': 7,
                   'archived': False, 'data': {'repo': p.REPOSITORY.split('/', 1)[1], 'tag': p.TAG,
                        'source_commit': 'a' * 40, 'hardware_profiles': ['x4']}}
        plan = {'release_revision': 7, 'catalog_revision': 7, 'revision': 0, 'payload_manifest': None, 'context': None}
        return {'observed_at': datetime.now(timezone.utc).isoformat(), 'source': 'catalog', 'release': release,
                'payload_plan': plan, 'raw_response_sha256': p.sha(p.canonical({'release': release, 'payload_plan': plan}))}

    def test_current_catalog_revision_not_assumed_one(self):
        receipt = self.catalog_receipt()
        self.assertEqual(p.fresh_catalog(receipt, '123456', 'a' * 40)['revision'], 7)
        for at in ((datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat(),
                   (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()):
            with self.assertRaisesRegex(ValueError, 'Fresh current catalog'):
                p.fresh_catalog({**receipt, 'observed_at': at}, '123456', 'a' * 40)

    def test_catalog_response_and_revision_mismatches_rejected(self):
        for target, key, value in [('release', 'revision', True), ('release', 'revision', 0),
                                   ('payload_plan', 'release_revision', 8), ('payload_plan', 'catalog_revision', 8),
                                   ('payload_plan', 'revision', True), ('release', 'archived', True),
                                   ('payload_plan', 'payload_manifest', {'existing': True})]:
            receipt = self.catalog_receipt(); receipt[target][key] = value
            receipt['raw_response_sha256'] = p.sha(p.canonical({k: receipt[k] for k in ('release', 'payload_plan')}))
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                p.fresh_catalog(receipt, '123456', 'a' * 40)
        receipt = self.catalog_receipt(); receipt['release']['revision'] = 8
        with self.assertRaisesRegex(ValueError, 'response digest differs'):
            p.fresh_catalog(receipt, '123456', 'a' * 40)
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            p.fresh_catalog(self.catalog_receipt(), '123456', 'b' * 40)

    def test_installed_bootstrap_evidence_required(self):
        contract = p.load_json(p.CONTRACT)
        evidence = {'firmware_id': p.BOOTSTRAP, 'confirmed_installed': True, 'product_id': 'xteink-x4-pro',
                    'factory_sha256': contract['baseline']['factory']['sha256'], 'source': 'user-confirmation',
                    'confirmed_at': datetime.now(timezone.utc).isoformat(), 'evidence_reference': 'test-only-owner-message'}
        p.check_installed(evidence, contract)
        for key, value in [('confirmed_installed', False), ('firmware_id', p.TAG), ('factory_sha256', 'f' * 64),
                           ('source', 'assumed-from-release'), ('evidence_reference', '')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.check_installed({**evidence, key: value}, contract)

    def test_fixture_baseline_cannot_masquerade_as_124(self):
        admission = {'version': '0.1.123', 'release_tag': p.TAG}
        with self.assertRaisesRegex(ValueError, 'qualified .124 identity'):
            p.check_qualification(admission, {}, b'{}', b'.123', b'zip', self.files)
        admission.update(version=p.VERSION, native_marker=p.NATIVE_MARKER)
        with self.assertRaisesRegex(ValueError, 'native marker missing'):
            p.check_qualification(admission, {}, b'{}', b'.123', b'zip', self.files)

    def candidate_evidence(self, native=None):
        if native is None:
            native = (p.NATIVE_MARKER.encode() + b'\x00X4_SOURCE=' + b'a' * 40 +
                      b'\x00RTE_SOURCE=' + p.RUNTIME_REVISION.encode() + b'\x00synthetic-unit-test-native')
        factory = bytearray(16 * 1024 * 1024)
        factory[0x10000:0x10000 + len(native)] = native
        factory = bytes(factory)
        archive_path = self.zip_input(); archive = archive_path.read_bytes()
        inventory = {name: p.record(data) for name, data in self.files.items()}
        mapping = {'provider': 'x4pro-sd', 'instance': 9, 'wire_namespace': 12, 'production_graph_binding_passed': True}
        q = {'status': 'software-qualified-candidate-hardware-pending',
             'input_lock': {'candidate_version': p.VERSION, 'sources': {'product': {'revision': 'a' * 40},
                            'runtime': {'revision': p.RUNTIME_REVISION}}},
             'artifacts': {p.FACTORY: p.record(factory), p.SD_ARCHIVE: p.record(archive), 'firmware.bin': p.record(native)},
             'sd_preservation': {'files': inventory}, 'admission': {'retained_sd_graph_binding': mapping},
             'admission_sanitized': {'retained_sd_graph_binding': copy.deepcopy(mapping)}}
        qraw = p.canonical(q)
        a = {'version': p.VERSION, 'release_tag': p.TAG, 'native_marker': p.NATIVE_MARKER, 'source_commit': 'a' * 40,
             'runtime_revision': p.RUNTIME_REVISION, 'product_id': 'xteink-x4-pro', 'hardware_profile': 'x4',
             'factory': p.record(factory), 'sd_archive': p.record(archive), 'qualification': p.record(qraw),
             'payload_files': inventory, 'publication_enabled': False}
        return a, q, qraw, factory, archive, archive_path

    def test_prepare_candidate_is_noninstallable_and_preserves_exact_bytes(self):
        a, q, qraw, factory, archive, path = self.candidate_evidence()
        factory_path = self.root / p.FACTORY; factory_path.write_bytes(factory)
        ap = self.root / 'admission.json'; ap.write_bytes(p.canonical(a))
        qp = self.root / 'qualification.json'; qp.write_bytes(qraw)
        out = self.root / 'candidate-fixture'
        with mock.patch.object(p, 'live_release', side_effect=AssertionError('candidate fixture must stay offline')):
            report = p.build(schema=self.schema, factory=factory_path, sd_archive=path, output=out,
                             operation='create', mode='prepare-candidate', admission=ap, qualification=qp)
        self.assertTrue(report['candidate_fixture_not_release'])
        self.assertFalse(report['baseline_only_not_124'])
        self.assertTrue(report['fixture'])
        self.assertFalse((out / 'descriptor.json').exists())
        container = next(out.glob('*.zip'))
        with zipfile.ZipFile(container) as z:
            m = p.parse(z.read('manifest.json'))
            self.assertEqual(m['firmware']['version'], p.VERSION)
            self.assertEqual(m['catalog_release']['source_commit'], 'a' * 40)
            self.assertEqual(m['catalog_release']['release_id'], '1')
            self.assertEqual(m['catalog_release']['tag'], p.TAG)
            self.assertEqual(m['product']['hardware_revisions'], ['fixture-unspecified'])
            self.assertEqual(z.read('firmware/' + p.FACTORY), factory)
            for row in m['payload']['files']:
                self.assertEqual(z.read(row['source']), self.files[row['destination'][1:]])
        with self.assertRaisesRegex(ValueError, 'fixture is not installable'):
            self.v.validate_container(container, p.load_json(out / 'context.json'))

    def test_candidate_qualification_checks_exact_bytes_and_mapping(self):
        a, q, qraw, factory, archive, _ = self.candidate_evidence()
        p.check_qualification(a, q, qraw, factory, archive, self.files, require_hardware_revision=False)
        for group, key, value in [('admission', 'wire_namespace', 9), ('admission', 'instance', 12),
                                  ('admission_sanitized', 'provider', 'internal-store'),
                                  ('admission_sanitized', 'production_graph_binding_passed', False)]:
            changed = copy.deepcopy(q); changed[group]['retained_sd_graph_binding'][key] = value
            raw = p.canonical(changed); admission = {**a, 'qualification': p.record(raw)}
            with self.subTest(group=group, key=key), self.assertRaisesRegex(ValueError, 'wire12/provider9'):
                p.check_qualification(admission, changed, raw, factory, archive, self.files, require_hardware_revision=False)
        with self.assertRaisesRegex(ValueError, 'qualification evidence differs'):
            p.check_qualification(a, q, qraw + b' ', factory, archive, self.files, require_hardware_revision=False)
        with self.assertRaisesRegex(ValueError, 'factory differs'):
            p.check_qualification(a, q, qraw, factory[:-1] + b'x', archive, self.files, require_hardware_revision=False)

    def test_native_product_source_is_not_just_json_identity(self):
        a, q, _, factory, archive, _ = self.candidate_evidence()
        a['source_commit']='b'*40
        q['input_lock']['sources']['product']['revision']='b'*40
        raw=p.canonical(q);a['qualification']=p.record(raw)
        with self.assertRaisesRegex(ValueError, 'Embedded native product source'):
            p.check_qualification(a,q,raw,factory,archive,self.files,require_hardware_revision=False)

    def test_native_source_markers_missing_conflicting_or_mismatched_rejected(self):
        native=(p.NATIVE_MARKER.encode()+b'\x00X4_SOURCE='+b'a'*40+
                b'\x00RTE_SOURCE='+p.RUNTIME_REVISION.encode()+b'\x00')
        for name,expected in ((b'X4_SOURCE=',b'a'*40),(b'RTE_SOURCE=',p.RUNTIME_REVISION.encode())):
            for changed in (native.replace(name,b'NOT_SOURCE='),
                            native.replace(name+expected,name+b'b'*40),
                            native+name+b'c'*40+b'\x00'):
                with self.subTest(name=name,changed=changed[-42:]):
                    a,q,raw,factory,archive,_=self.candidate_evidence(changed)
                    with self.assertRaisesRegex(ValueError, 'Embedded native .* source'):
                        p.check_qualification(a,q,raw,factory,archive,self.files,require_hardware_revision=False)

    def test_final_qualification_requires_independently_admitted_hardware_revision(self):
        a, q, qraw, factory, archive, _ = self.candidate_evidence()
        for revision in (None, '', 'fixture-unspecified'):
            candidate = {**a, 'hardware_revision': revision}
            with self.subTest(revision=revision), self.assertRaisesRegex(ValueError, 'independently admitted board revision'):
                p.check_qualification(candidate, q, qraw, factory, archive, self.files)

    def test_native_marker_outside_native_image_cannot_spoof_124(self):
        a, q, qraw, factory, archive, _ = self.candidate_evidence()
        damaged = bytearray(factory); damaged[0x10000] ^= 1
        damaged[-len(p.NATIVE_MARKER):] = p.NATIVE_MARKER.encode()
        damaged = bytes(damaged)
        q['artifacts'][p.FACTORY] = p.record(damaged)
        qraw = p.canonical(q); a.update(factory=p.record(damaged), qualification=p.record(qraw))
        with self.assertRaisesRegex(ValueError, 'native identity differs inside factory'):
            p.check_qualification(a, q, qraw, damaged, archive, self.files, require_hardware_revision=False)

    @unittest.skipUnless(os.environ.get('X4_PAIR_BASELINE_INPUTS'), 'Set X4_PAIR_BASELINE_INPUTS for full 77-file audit')
    def test_published_77_file_fixture_roundtrip_and_no_final_descriptor(self):
        inputs = Path(os.environ['X4_PAIR_BASELINE_INPUTS'])
        output = self.root / 'full-fixture'
        result = p.build(schema=self.schema, factory=inputs / p.FACTORY,
                         sd_archive=inputs / 'X4-0.1.121-Complete-SD-Keep-Existing.zip', output=output,
                         operation='replace')
        self.assertTrue(result['fixture']); self.assertFalse(result['publication_authorized'])
        self.assertEqual(result['result']['file_count'], 77)
        self.assertEqual(result['result']['bytes'], 10827862)
        self.assertFalse((output / 'descriptor.json').exists())
        self.assertTrue((output / 'NONINSTALLABLE-fixture-descriptor.json').exists())
        with self.assertRaisesRegex(ValueError, 'fixture is not installable'):
            self.v.validate_container(next(output.glob('*.zip')), p.load_json(output / 'context.json'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
