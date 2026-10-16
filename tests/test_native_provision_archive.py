#!/usr/bin/env python3
"""Bounded archive-custody controls; no network, target build or device access."""
import base64
import copy
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
import urllib.request
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import native_provision_archive as a


def zip_bytes(rows):
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in rows:
                archive.writestr(name, content)
    return output.getvalue()


def metadata(c):
    pin = c['run']
    repository = {'id': pin['repository_id'], 'full_name': a.REPOSITORY}
    job = {'id': pin['job_id'], 'run_id': pin['id'], 'run_attempt': pin['attempt'],
           'head_sha': c['source_revision'], 'name': 'qualify', 'status': 'completed',
           'conclusion': 'failure', 'started_at': '2026-10-16T21:44:02Z',
           'completed_at': '2026-10-16T21:57:57Z',
           'steps': [{'name': name, 'status': 'completed', 'conclusion': result}
                     for name, result in a.EXPECTED_STEPS.items()]}
    artifact = {'id': c['artifact']['id'], 'name': c['artifact']['name'],
                'size_in_bytes': c['artifact']['bytes'], 'digest': 'sha256:' + c['artifact']['sha256'],
                'expired': False, 'created_at': '2026-10-16T21:57:55Z',
                'workflow_run': {'id': pin['id'], 'head_sha': c['source_revision'],
                                 'head_branch': pin['head_branch'], 'repository_id': pin['repository_id'],
                                 'head_repository_id': pin['repository_id']}}
    return {'run': {'id': pin['id'], 'run_attempt': pin['attempt'], 'workflow_id': pin['workflow_id'],
                    'path': a.WORKFLOW, 'head_sha': c['source_revision'], 'head_branch': pin['head_branch'],
                    'event': 'pull_request', 'status': 'completed', 'conclusion': 'failure',
                    'repository': repository, 'head_repository': repository,
                    'pull_requests': [{'number': pin['pull_request'],
                                       'head': {'sha': c['source_revision'], 'ref': pin['head_branch'],
                                                'repo': repository}, 'base': {'repo': repository}}]},
            'jobs': {'total_count': 1, 'jobs': [job]},
            'artifacts': {'total_count': 2, 'artifacts': [artifact, {'id': 2}]},
            'commit': {'sha': c['source_revision'], 'commit': {'tree': {'sha': c['source_tree']}}},
            'workflow': b'synthetic producer workflow\n'}


class Controls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.c = a.contract()
        self.c['run']['workflow_sha256'] = a.sha(b'synthetic producer workflow\n')
        self.raw = zip_bytes([('build/payload.bin', b'unchanged target bytes'), ('logs/empty.txt', b'')])
        self.pin(self.raw)

    def pin(self, raw):
        self.raw = raw
        self.c['artifact'].update(bytes=len(raw), sha256=a.sha(raw))
        self.archive = self.root / 'original.zip'
        self.archive.write_bytes(raw)
        self.metadata = metadata(self.c)
        self.contract = self.root / 'contract.json'
        self.contract.write_bytes(a.encoded(self.c))
        self.evidence = self.root / 'metadata'
        self.evidence.mkdir(exist_ok=True)
        for name, value in self.metadata.items():
            (self.evidence / (name + ('.yml' if name == 'workflow' else '.json'))).write_bytes(
                value if name == 'workflow' else a.encoded(value))

    def proof(self):
        return a.verify_local(self.contract, self.archive, self.evidence)

    def test_contract_is_explicit_and_exact(self):
        c = a.contract()
        self.assertIs(type(c['qualification_enabled']), bool)
        self.assertEqual(c['run']['id'], 38971323967)
        self.assertEqual(c['artifact']['id'], 12077257848)
        self.assertEqual(c['artifact']['bytes'], 782287221)

    def test_valid_metadata_keeps_failed_producer(self):
        a.verify_metadata(self.c, self.metadata)
        self.assertFalse(self.proof().receipt['fresh_build'])
        self.assertEqual(self.proof().receipt['producer_run']['conclusion'], 'failure')

    def test_historical_identity_ignores_live_pr_sha(self):
        self.metadata['run']['pull_requests'][0]['head']['sha'] = 'f' * 40
        a.verify_metadata(self.c, self.metadata)
        self.metadata['run']['pull_requests'][0]['head']['sha'] = 'not-an-sha'
        with self.assertRaises(ValueError): a.verify_metadata(self.c, self.metadata)

    def test_producer_identity_mutations_fail(self):
        cases = [('run', 'id', 1), ('run', 'run_attempt', 2), ('run', 'head_sha', 'f' * 40),
                 ('run', 'workflow_id', 1), ('run', 'path', 'other.yml'),
                 ('run', 'conclusion', 'success'), ('run', 'event', 'push'),
                 ('run', 'status', 'in_progress'), ('run', 'head_branch', 'other')]
        for group, key, value in cases:
            with self.subTest(key=key):
                m = copy.deepcopy(self.metadata); m[group][key] = value
                with self.assertRaises(ValueError): a.verify_metadata(self.c, m)

    def test_job_identity_and_early_steps_cannot_be_relabelled(self):
        for key, value in [('id', 1), ('run_id', 1), ('run_attempt', 2), ('head_sha', 'f' * 40),
                           ('conclusion', 'success'), ('name', 'other')]:
            with self.subTest(key=key):
                m = copy.deepcopy(self.metadata); m['jobs']['jobs'][0][key] = value
                with self.assertRaises(ValueError): a.verify_metadata(self.c, m)
        for index in range(len(a.EXPECTED_STEPS)):
            m = copy.deepcopy(self.metadata)
            m['jobs']['jobs'][0]['steps'][index]['conclusion'] = 'cancelled'
            with self.assertRaises(ValueError): a.verify_metadata(self.c, m)

    def test_archive_metadata_mutations_fail(self):
        for key, value in [('id', 1), ('name', 'other'), ('size_in_bytes', 1),
                           ('digest', 'sha256:' + 'f' * 64), ('expired', True),
                           ('created_at', '2026-10-16T21:58:00Z')]:
            with self.subTest(key=key):
                m = copy.deepcopy(self.metadata); m['artifacts']['artifacts'][0][key] = value
                with self.assertRaises(ValueError): a.verify_metadata(self.c, m)
        for key, value in [('id', 1), ('head_sha', 'f' * 40), ('head_repository_id', 1)]:
            m = copy.deepcopy(self.metadata); m['artifacts']['artifacts'][0]['workflow_run'][key] = value
            with self.assertRaises(ValueError): a.verify_metadata(self.c, m)

    def test_incomplete_metadata_and_wrong_tree_workflow_reject(self):
        for mutate in [lambda m: m['jobs'].update(total_count=2),
                       lambda m: m['artifacts'].update(total_count=3),
                       lambda m: m['commit']['commit']['tree'].update(sha='f' * 40),
                       lambda m: m.update(workflow=b'other'),
                       lambda m: m['run']['head_repository'].update(id=1)]:
            m = copy.deepcopy(self.metadata); mutate(m)
            with self.assertRaises(ValueError): a.verify_metadata(self.c, m)

    def test_archive_digest_and_size_rechecked(self):
        proof = self.proof()
        self.archive.write_bytes(self.raw[:-1] + b'x')
        with self.assertRaises(ValueError): a.extract_verified(proof, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_streaming_extraction_retains_original_zip(self):
        proof = self.proof()
        original_read = Path.read_bytes
        def forbidden(path):
            self.assertNotEqual(path, self.archive, 'Original ZIP must never be read into memory')
            return original_read(path)
        with mock.patch.object(Path, 'read_bytes', forbidden):
            inventory = a.extract_verified(proof, self.root / 'restored')
        self.assertEqual(inventory['build/payload.bin']['sha256'], a.sha(b'unchanged target bytes'))
        self.assertEqual(inventory['logs/empty.txt'], {'bytes': 0, 'sha256': a.sha(b'')})
        self.assertEqual(self.archive.read_bytes(), self.raw)

    def test_unsafe_names_fail_before_extraction(self):
        for name in ('.', '../escape', '/escape', 'C:/escape', 'a\\escape', 'a//b', 'a/./b', 'a/../b', 'a\nfile'):
            with self.subTest(name=name):
                self.pin(zip_bytes([(name, b'bad')]))
                out = self.root / 'out'
                with self.assertRaises(ValueError): a.extract_verified(self.proof(), out)
                self.assertFalse(out.exists())

    def test_nul_filename_and_encryption_reject_before_output(self):
        self.pin(zip_bytes([('aXb', b'content')]).replace(b'aXb', b'a\0b'))
        with self.assertRaises(ValueError): a.extract_verified(self.proof(), self.root / 'out')
        raw = bytearray(zip_bytes([('file', b'content')]))
        for signature, offset in ((b'PK\x03\x04', 6), (b'PK\x01\x02', 8)):
            index = raw.index(signature) + offset
            raw[index] |= 1
        self.pin(bytes(raw))
        with self.assertRaises(ValueError): a.extract_verified(self.proof(), self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_nested_source_archives_remain_opaque(self):
        self.pin(zip_bytes([('source-evidence/sdk-source.tar.gz', b'opaque-not-a-tar')]))
        a.extract_verified(self.proof(), self.root / 'out')
        self.assertEqual((self.root / 'out/source-evidence/sdk-source.tar.gz').read_bytes(), b'opaque-not-a-tar')

    def test_duplicate_and_file_directory_collision_reject(self):
        for rows in [[('same', b'a'), ('same', b'b')], [('a', b'file'), ('a/b', b'child')],
                     [('a/b', b'child'), ('a', b'file')], [('a', b'file'), ('a/', b'')]]:
            self.pin(zip_bytes(rows))
            with self.assertRaises(ValueError): a.extract_verified(self.proof(), self.root / 'out')
            self.assertFalse((self.root / 'out').exists())

    def test_symlink_and_special_members_reject(self):
        for mode in (stat.S_IFLNK, stat.S_IFCHR, stat.S_IFIFO, stat.S_IFSOCK):
            row = zipfile.ZipInfo('member'); row.create_system = 3; row.external_attr = (mode | 0o777) << 16
            self.pin(zip_bytes([(row, b'outside')]))
            with self.assertRaises(ValueError): a.extract_verified(self.proof(), self.root / 'out')

    def test_directory_data_and_wrong_directory_mode_reject(self):
        self.pin(zip_bytes([('dir/', b'data'), ('dir/file', b'ok')]))
        with self.assertRaises(ValueError): a.extract_verified(self.proof(), self.root / 'out')
        row = zipfile.ZipInfo('dir/'); row.external_attr = (stat.S_IFREG | 0o644) << 16
        self.pin(zip_bytes([(row, b''), ('dir/file', b'ok')]))
        with self.assertRaises(ValueError): a.extract_verified(self.proof(), self.root / 'out')

    def test_archive_bounds_reject_before_output(self):
        for bound, value in [('MAX_MEMBERS', 1), ('MAX_EXPANSION', 3), ('MAX_MEMBER', 3)]:
            with self.subTest(bound=bound), mock.patch.object(a, bound, value):
                with self.assertRaises(ValueError): a.extract_verified(self.proof(), self.root / 'out')
                self.assertFalse((self.root / 'out').exists())

    def test_selected_export_is_bounded_and_requires_every_member(self):
        proof = self.proof()
        with self.assertRaises(ValueError): a.extract_verified(proof, self.root / 'missing', {'missing'})
        with mock.patch.object(a, 'MAX_SMALL', 1):
            with self.assertRaises(ValueError): a.extract_verified(proof, self.root / 'oversize', {'build/payload.bin'})
        selected = a.extract_verified(proof, self.root / 'small', {'build/payload.bin'})
        self.assertEqual(set(selected), {'build/payload.bin'})
        self.assertFalse((self.root / 'small/logs').exists())

    def test_existing_destination_is_never_overwritten(self):
        out = self.root / 'out'; out.mkdir(); sentinel = out / 'sentinel'; sentinel.write_bytes(b'keep')
        with self.assertRaises(ValueError): a.extract_verified(self.proof(), out)
        self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_symlink_destination_or_archive_reject(self):
        destination = self.root / 'link'; destination.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): a.extract_verified(self.proof(), destination / 'child')
        link = self.root / 'archive-link'; link.symlink_to(self.archive)
        with self.assertRaises(ValueError): a.verify_archive(self.c, link)

    def test_restored_hashes_and_inventory_are_rechecked(self):
        proof = self.proof(); out = self.root / 'restored'
        a.extract_verified(proof, out)
        c = copy.deepcopy(proof.contract); c['original_root'] = str(out)
        adjusted = a.VerifiedArchive(a._TOKEN, c, proof.archive, proof.metadata, proof.receipt, {})
        verified = a.verify_restored(adjusted, out)
        self.assertEqual(set(verified.inventory), {'build/payload.bin', 'logs/empty.txt'})
        (out / 'build/payload.bin').write_bytes(b'changed')
        with self.assertRaises(ValueError): a.verify_restored(adjusted, out)
        (out / 'build/payload.bin').write_bytes(b'unchanged target bytes')
        (out / 'build/added.o').write_bytes(b'new target object')
        with self.assertRaises(ValueError): a.verify_restored(adjusted, out)

    def test_detached_receipt_is_not_authority(self):
        forged = a.VerifiedArchive(object(), self.c, self.archive, self.metadata, {}, {})
        with self.assertRaises(ValueError): a.extract_verified(forged, self.root / 'out')
        with self.assertRaises(ValueError): a.verify_restored(forged, self.root / 'out')

    def test_redirect_never_forwards_token_and_rejects_http(self):
        request = urllib.request.Request('https://api.github.com/repos/' + a.REPOSITORY,
                                         headers={'Authorization': 'Bearer fixture-only'})
        redirected = a.HttpsRedirect().redirect_request(request, None, 302, '', {}, 'https://example.test/archive')
        self.assertFalse(redirected.has_header('Authorization'))
        for url in ('http://example.test/file', 'https://name:password@example.test/file'):
            with self.assertRaises(ValueError):
                a.HttpsRedirect().redirect_request(request, None, 302, '', {}, url)

    def test_download_rejects_wrong_hash_and_oversize(self):
        class Response(io.BytesIO):
            status = 200
        for raw in (b'other', self.raw + b'extra'):
            with self.subTest(size=len(raw)), mock.patch.object(a.Github, 'response', return_value=Response(raw)):
                with self.assertRaises(ValueError):
                    a.Github().download('fixture', self.root / ('download-' + str(len(raw))), self.c['artifact'])

    def test_download_streams_exact_bytes(self):
        class Response(io.BytesIO):
            status = 200
        with mock.patch.object(a.Github, 'response', return_value=Response(self.raw)):
            out = self.root / 'download'
            a.Github().download('fixture', out, self.c['artifact'])
            self.assertEqual(out.read_bytes(), self.raw)

    def test_fetch_checks_metadata_before_creating_output(self):
        parent = self
        class Api:
            def json(self, endpoint):
                if '/contents/' in endpoint:
                    return {'type': 'file', 'path': a.WORKFLOW, 'encoding': 'base64',
                            'content': base64.b64encode(parent.metadata['workflow']).decode()}
                key = ('jobs' if '/jobs?' in endpoint else 'artifacts' if '/artifacts?' in endpoint
                       else 'commit' if '/commits/' in endpoint else 'run')
                return parent.metadata[key]
            def download(self, endpoint, target, expected):
                target.write_bytes(parent.raw)
        self.metadata['run']['conclusion'] = 'success'
        with self.assertRaises(ValueError): a.fetch(self.c, self.root / 'fetch', Api())
        self.assertFalse((self.root / 'fetch').exists())
        self.metadata['run']['conclusion'] = 'failure'
        archive = a.fetch(self.c, self.root / 'fetch', Api())
        self.assertEqual(archive.read_bytes(), self.raw)
        a.verify_local(self.contract, archive, archive.parent)

    def test_workflow_is_read_only_and_contains_no_target_build(self):
        text = (a.ROOT / '.github/workflows/native-provision-123-requalify.yml').read_text()
        for forbidden in ('contents: write', 'gh release', 'cmake --build', 'idf.py', 'native_provision_build.py',
                          'build_home_provision.py', 'build_installed_apps.py', 'compile_native_serial_files_target.py'):
            self.assertNotIn(forbidden, text)
        self.assertIn('actions: read', text)
        self.assertIn('branches: [work/x4-qualification-recovery-123]', text)


if __name__ == '__main__':
    unittest.main()
