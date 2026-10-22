#!/usr/bin/env python3
"""X4 adapter checks only: no shared protocol test or hardware coverage claimed."""
import argparse
import copy
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import bind

P = argparse.ArgumentParser()
P.add_argument('--matrix', type=Path, required=True)
P.add_argument('--artifact', type=Path, required=True)
ARGS, OTHER = P.parse_known_args()
LOCK = bind.load((bind.HERE / 'inputs.json').read_bytes())
RAW = ARGS.artifact.read_bytes()
MATRIX, TEMPLATE = bind.audit(LOCK, bind.PRODUCT, ARGS.matrix, RAW)
MEMBERS = bind.zip_members(RAW)
MANIFEST_RAW = MEMBERS[LOCK['candidate']['fixture_manifest_member']]
MANIFEST = bind.load(MANIFEST_RAW)
PAYLOAD = bind.zip_members(MEMBERS['X4-0.1.124-Complete-SD-Keep-Existing.zip'])
SHARED = ARGS.matrix / LOCK['shared']['directory']
spec = importlib.util.spec_from_file_location('shared_review', SHARED / 'review_result.py')
REVIEW = importlib.util.module_from_spec(spec)
spec.loader.exec_module(REVIEW)


class BindingTests(unittest.TestCase):
    def test_actual_source_artifact_binding(self):
        self.assertEqual(len(PAYLOAD), 78)
        self.assertEqual(sum(map(len, PAYLOAD.values())), 11006894)

    def test_actual_archive_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Actions artifact'):
            bind.audit(LOCK, bind.PRODUCT, ARGS.matrix, RAW[:-1] + bytes([RAW[-1] ^ 1]))

    def test_actual_archive_truncation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Actions artifact'):
            bind.audit(LOCK, bind.PRODUCT, ARGS.matrix, RAW[:-1])

    def test_source_pin_tamper_rejected(self):
        changed = copy.deepcopy(LOCK)
        changed['product']['files']['profiles/native-paired-124.cmake'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            bind.audit(changed, bind.PRODUCT, ARGS.matrix, RAW)

    def test_shared_pin_tamper_rejected(self):
        changed = copy.deepcopy(LOCK)
        changed['shared']['files']['matrix.json'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            bind.audit(changed, bind.PRODUCT, ARGS.matrix, RAW)

    def test_missing_payload_rejected(self):
        changed = dict(PAYLOAD); changed.pop(next(iter(changed)))
        with self.assertRaisesRegex(ValueError, 'path set'):
            bind.check_payload(changed, LOCK['candidate']['payload_files'])

    def test_extra_payload_rejected(self):
        changed = dict(PAYLOAD); changed['extra'] = b''
        with self.assertRaisesRegex(ValueError, 'path set'):
            bind.check_payload(changed, LOCK['candidate']['payload_files'])

    def test_length_and_same_length_hash_tamper_rejected(self):
        path = next(iter(PAYLOAD))
        for value in (PAYLOAD[path][:-1], bytes([PAYLOAD[path][0] ^ 1]) + PAYLOAD[path][1:]):
            with self.subTest(length=len(value)):
                changed = dict(PAYLOAD); changed[path] = value
                with self.assertRaises(ValueError):
                    bind.check_payload(changed, LOCK['candidate']['payload_files'])

    def test_unsupported_order_rejected(self):
        changed = copy.deepcopy(MANIFEST); changed['plan']['order'] = ['payload', 'firmware', 'verify']
        with self.assertRaisesRegex(ValueError, 'order'):
            bind.check_plan(changed, LOCK['candidate'])

    def test_provider_instance_as_wire_rejected(self):
        changed = copy.deepcopy(MANIFEST); changed['payload']['bindings'][0]['namespace_id'] = '9'
        with self.assertRaisesRegex(ValueError, 'namespace confusion'):
            bind.check_plan(changed, LOCK['candidate'])

    def test_false_flash_preservation_rejected(self):
        changed = copy.deepcopy(MANIFEST); changed['firmware']['install']['volume_effects'][0]['effect'] = 'preserved'
        with self.assertRaisesRegex(ValueError, 'External flash effect'):
            bind.check_plan(changed, LOCK['candidate'])

    def test_duplicate_manifest_file_rejected(self):
        changed = copy.deepcopy(MANIFEST); changed['payload']['files'][-1] = changed['payload']['files'][0]
        with self.assertRaisesRegex(ValueError, 'uniqueness'):
            bind.check_plan(changed, LOCK['candidate'])

    def test_shared_case_or_variant_removal_rejected(self):
        for variant in (False, True):
            changed = copy.deepcopy(TEMPLATE)
            if variant: changed['cases'][0]['variants'].pop()
            else: changed['cases'].pop()
            with self.assertRaisesRegex(ValueError, 'coverage mismatch'):
                bind.draft(LOCK, MATRIX, changed)

    def test_unexecuted_schema(self):
        result = bind.draft(LOCK, MATRIX, TEMPLATE)
        self.assertEqual(len(result['cases']), 46)
        self.assertEqual(sum(len(x['variants']) for x in result['cases']), 85)
        self.assertEqual(len(result['file_results']), 78)
        self.assertEqual(result['hardware_status'], 'not_tested')
        self.assertTrue(all(v is None for v in result['x4_preparation']['stop_gates'].values()))
        for key in ('firmware_before', 'firmware_after', 'release_id', 'catalog_revision',
                    'hardware_revision', 'device_identifier', 'manifest_sha256', 'started_at'):
            self.assertIsNone(result[key])
        for case in result['cases']:
            self.assertEqual(case['status'], 'not_run')
            self.assertTrue(all(v['status'] == 'not_run' for v in case['variants']))
        self.assertTrue(all(row['operation'] is None and row['actual_sha256'] is None and
                            row['status'] == 'unverified' for row in result['file_results']))

    def test_draft_cannot_pass_shared_report_checker(self):
        result = bind.draft(LOCK, MATRIX, TEMPLATE)
        self.assertTrue(REVIEW.review(result, MANIFEST, MANIFEST_RAW))

    def test_generated_bytes_are_reproducible(self):
        self.assertEqual((bind.HERE / 'draft.json').read_bytes(), bind.encoded(bind.draft(LOCK, MATRIX, TEMPLATE)))

    def test_duplicate_json_and_zip_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            bind.load('{"id":1,"id":2}')
        buffer = io.BytesIO()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(buffer, 'w') as z:
                z.writestr('same', b'1'); z.writestr('same', b'2')
        with self.assertRaisesRegex(ValueError, 'Duplicate ZIP'):
            bind.zip_members(buffer.getvalue())


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + OTHER, verbosity=2)
