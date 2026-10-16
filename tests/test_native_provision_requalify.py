#!/usr/bin/env python3
"""Offline controls for separate archive authority, not CI attestation."""
import copy
from contextlib import ExitStack
from types import SimpleNamespace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_provision_requalify as q


class Controls(unittest.TestCase):
    def test_detached_receipts_and_foreign_tokens_rejected(self):
        for value in ({'fresh_build': True}, None, object()):
            with self.assertRaises(ValueError):
                q.validate_archived_evidence(value, {}, Path('/build'), Path('/compiler'))
        value = q.ArchivedEvidence(); value.token = object()
        with self.assertRaises(ValueError):
            q.validate_archived_evidence(value, {}, Path('/build'), Path('/compiler'))

    def test_archive_authentication_and_safe_restore_precede_receipt_reads(self):
        local = mock.Mock(return_value='verified archive')
        restored = mock.Mock(side_effect=ValueError('unsafe restored archive'))
        module = SimpleNamespace(verify_local=local, verify_restored=restored)
        with mock.patch.dict(sys.modules, {'native_provision_archive': module}):
            with self.assertRaisesRegex(ValueError, 'unsafe restored archive'):
                q.authenticate(Path('/archive'), Path('/metadata'), Path('/restored'), {}, Path('/compiler'))
        local.assert_called_once_with(q.CONTRACT, Path('/archive'), Path('/metadata'))
        restored.assert_called_once_with('verified archive', Path('/restored'))

    def test_dependency_hash_size_and_presence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'object.o'; path.write_bytes(b'original')
            rows = {str(path): {**q.row(path), 'kind': 'generated'}}
            q.verify_rows(rows)
            for key, value in [('bytes', 1), ('sha256', '0' * 64)]:
                bad = copy.deepcopy(rows); bad[str(path)][key] = value
                with self.assertRaises(ValueError): q.verify_rows(bad)
            path.unlink()
            with self.assertRaises(ValueError): q.verify_rows(rows)

    def test_qualifier_diff_rejects_native_package_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid')
            (root / 'native.cpp').write_text('original native source')
            (root / 'scripts').mkdir()
            qualifier = root / 'scripts/native_provision_qualification.py'; qualifier.write_text('before')
            git('add', '.'); git('commit', '-qm', 'producer')
            producer = git('rev-parse', 'HEAD'); tree = git('rev-parse', 'HEAD^{tree}')
            producer_root = root / 'producer'
            git('worktree', 'add', '--detach', str(producer_root), producer)
            # Worktree is untracked at this location; exclude only this fixture tree.
            (root / '.git/info/exclude').write_text('/producer/\n')
            qualifier.write_text('reviewed qualifier fix')
            git('add', '.'); git('commit', '-qm', 'qualifier')
            with mock.patch.object(q, 'PRODUCER', producer), mock.patch.object(q, 'PRODUCER_TREE', tree):
                result = q.qualifier_diff(producer_root, root)
                self.assertEqual(set(result['changed_files']), {'scripts/native_provision_qualification.py'})
                (root / 'native.cpp').write_text('changed production input')
                git('add', '.'); git('commit', '-qm', 'invalid production change')
                with self.assertRaises(ValueError): q.qualifier_diff(producer_root, root)

    def test_complete_archive_validation_and_mutation_rejection(self):
        # Synthetic private-token fixture tests the validator only. It does not
        # call authenticate or claim that JSON alone authorizes real delivery.
        for mutation in (None, 'object', 'tool', 'package', 'receipt', 'lock', 'qualifier'):
            with tempfile.TemporaryDirectory() as temp, ExitStack() as patches:
                root = Path(temp); build = root / 'build'; packages = root / 'build-packages'
                (build / 'native-build-evidence').mkdir(parents=True); packages.mkdir()
                obj = build / 'firmware.elf'; obj.write_bytes(b'original ELF')
                compiler = root / 'compiler'; compiler.write_bytes(b'original compiler')
                app = packages / 'app.elf'; app.write_bytes(b'original application')
                package = dict(same_process_build=True, sources={}, files={'app.elf': q.row(app)},
                               compilers={'gcc': {'path': str(compiler), 'sha256': q.row(compiler)['sha256']}})
                closure = dict(fresh_build=True, same_process_qualification=True, sources={},
                               files={str(obj): q.row(obj)}, tools={'gcc': {'path': str(compiler), **q.row(compiler)}},
                               artifacts={'firmware_elf': q.row(obj)})
                lock = dict(sources={}, package_build=package,
                            native_files={'firmware_elf': {'path': obj.name, **q.row(obj)}})
                proof = q.ArchivedEvidence(); proof.token = q._TOKEN
                proof.root = root; proof.sources = {'product': root}; proof.compiler = compiler
                proof.verified_archive = object(); proof.receipt = {'qualifier': {}}
                proof.lock = lock; proof.package_receipt = package; proof.build_report = closure
                for attr, path, value in [
                    ('lock_bytes', build / 'native-build-evidence/source-lock.json', lock),
                    ('build_report_bytes', build / 'native-build-evidence/build-closure.json', closure),
                    ('package_receipt_bytes', packages / 'package-build-receipt.json', package)]:
                    raw = q.recipe.encoded(value); path.write_bytes(raw); setattr(proof, attr, raw)
                proof.inventory = {p.relative_to(root).as_posix(): q.row(p) for p in root.rglob('*') if p.is_file()}
                patches.enter_context(mock.patch.dict(sys.modules, {'native_provision_archive': SimpleNamespace(verify_restored=lambda *a: None)}))
                patches.enter_context(mock.patch.object(q.recipe, 'verify_sources'))
                patches.enter_context(mock.patch.object(q.recipe, 'checked_artifacts'))
                patches.enter_context(mock.patch.object(q, 'qualifier_diff', return_value={'changed': True} if mutation == 'qualifier' else {}))
                patches.enter_context(mock.patch.object(q, 'package_values', return_value={'default.elf': app.read_bytes()}))
                if mutation in ('object', 'tool', 'package'):
                    {'object': obj, 'tool': compiler, 'package': app}[mutation].write_bytes(b'changed')
                if mutation == 'receipt': (packages / 'package-build-receipt.json').write_bytes(b'{}')
                checked_lock = dict(lock, schema=999) if mutation == 'lock' else lock
                call = lambda: q.validate_archived_evidence(proof, proof.sources, build, compiler, checked_lock)
                if mutation:
                    with self.assertRaises(ValueError): call()
                else:
                    self.assertEqual(call(), (closure, {'default.elf': b'original application'}))

    def test_requalify_does_not_build_native_or_packages(self):
        text = (ROOT / 'scripts/native_provision_requalify.py').read_text()
        for forbidden in ('collect_build_proof(', 'build_packages(', 'BuildProof()', 'PackageProof()',
                          'build_commands(', 'compile_runtime_platform_capacity_target.py'):
            self.assertNotIn(forbidden, text)
        self.assertIn('native_rebuilt', text)
        self.assertIn('packages_rebuilt', text)
        self.assertIn("'same_process_qualification': False", text)


if __name__ == '__main__':
    unittest.main()
