#!/usr/bin/env python3
"""Offline Files-only custody, authority, archive, and flash-preservation tests."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import compose_files_092 as c


class FilesCustody(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.files = self.root / 'files'; self.files.mkdir()
        self.system = self.root / 'system'; self.system.mkdir()
        sources = {'Apps/file_browser.c': b'synthetic Files C',
                   'Apps/native/file_browser.json': b'synthetic source manifest'}
        c.write_files(self.system, sources)
        self.manifest = dict(id='file-browser', version=c.FILES_VERSION, file_name='file_browser.elf',
                             requires=[dict(capability='test.' + str(i), api=1) for i in range(16)])
        self.grants = [dict(capability='test.' + str(i), api=1, instance_id=i + 1) for i in range(16)]
        self.boot = dict(installation=dict(settings_sd=True),
            app_capabilities=[dict(manifest='file_browser.json', grants=self.grants)] +
                             [dict(manifest='app%d.json' % i) for i in range(25)],
            drivers=[dict(manifest='driver%d/manifest.json' % i) for i in range(32)])
        self.old = {'file_browser.json': c.encoded(dict(self.manifest, version='1.5.28')),
                    'file_browser.elf': b'old ELF', 'boot.json': c.encoded(self.boot),
                    'cohort.json': c.encoded(dict(version='0.1.90', firmware_sha256='a' * 64)),
                    'ui-text/driver.elf': b'unchanged text provider',
                    'ui-scene/driver.elf': b'unchanged scene provider'}
        self.raw = b'\x7fELFsynthetic new file browser'
        self.build = dict(version=c.FILES_VERSION, repository_commit=c.SYSTEM, working_tree_dirty=False,
            sha256=c.sha(self.raw), size_bytes=len(self.raw), defines=['-DFILES'], build_defines=['-DFILES'],
            required_grants=self.grants, requested_capabilities=self.manifest['requires'], grant_count=16,
            grant_bindings=self.grants, profile='x4-native-time', storage_selection=dict(primary='volume9'),
            source_sha256=c.inventory(sources), protected_settings=dict(root='/RTECFG', listing_open_mutation_copy=True),
            file_sharing=dict(protected_settings=dict(direct_recursive_and_peer=True)))
        self.previous = copy.deepcopy(self.build)
        self.lock = dict(product_version=c.VERSION, files_version=c.FILES_VERSION,
                         system_commit=c.SYSTEM, system_tree=c.SYSTEM_TREE)
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, relock=True):
        self.artifacts = {'file_browser.json': c.encoded(self.manifest), 'file_browser.elf': self.raw,
                          'file_browser-build-record.json': c.encoded(self.build)}
        c.write_files(self.files, self.artifacts)
        if relock:
            self.lock['artifacts'] = c.inventory(self.artifacts)

    def validate(self):
        return c.validate_files(self.files, self.system, self.old, self.previous, self.lock)

    def test_exact_input_and_16_grants_accepted(self):
        artifacts, build = self.validate()
        self.assertEqual(artifacts, self.artifacts)
        self.assertEqual(build['grant_count'], 16)

    def test_only_files_and_cohort_change(self):
        self.validate()
        new = c.changed_store(self.old, self.artifacts, 'b' * 40)
        self.assertEqual({n for n in new if new[n] != self.old[n]}, c.ALLOWED)
        self.assertEqual(new['boot.json'], self.old['boot.json'])
        self.assertEqual(new['ui-scene/driver.elf'], self.old['ui-scene/driver.elf'])
        self.assertEqual(new['ui-text/driver.elf'], self.old['ui-text/driver.elf'])
        self.assertEqual(json.loads(new['cohort.json']), dict(version=c.VERSION, firmware_sha256='a' * 64, source_revision='b' * 40))

    def test_unlocked_elf_change_rejected(self):
        (self.files / 'file_browser.elf').write_bytes(b'unrecorded')
        with self.assertRaisesRegex(ValueError, 'qualification lock'): self.validate()

    def test_changed_receipt_rejected(self):
        self.build['compiler'] = 'unrecorded'; self.save(relock=False)
        with self.assertRaisesRegex(ValueError, 'qualification lock'): self.validate()

    def test_receipt_elf_binding_rejected(self):
        self.build['sha256'] = '0' * 64; self.save()
        with self.assertRaisesRegex(ValueError, 'receipt mismatch'): self.validate()

    def test_dirty_build_rejected(self):
        self.build['working_tree_dirty'] = True; self.save()
        with self.assertRaisesRegex(ValueError, 'receipt mismatch'): self.validate()

    def test_wrong_source_commit_rejected(self):
        self.build['repository_commit'] = '0' * 40; self.save()
        with self.assertRaisesRegex(ValueError, 'receipt mismatch'): self.validate()

    def test_wrong_source_tree_lock_rejected(self):
        self.lock['system_tree'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'wrong source/version'): self.validate()

    def test_wrong_version_rejected(self):
        self.manifest['version'] = '1.5.29'; self.save()
        with self.assertRaisesRegex(ValueError, 'Files version'): self.validate()

    def test_manifest_authority_rejected(self):
        self.manifest['requires'].append(dict(capability='new-grant', api=1)); self.save()
        with self.assertRaisesRegex(ValueError, 'authority changed'): self.validate()

    def test_profile_change_rejected(self):
        self.build['defines'].append('-DNEW_PROFILE'); self.save()
        with self.assertRaisesRegex(ValueError, 'profile/grants changed'): self.validate()

    def test_seventeenth_grant_rejected(self):
        self.build['required_grants'].append(dict(capability='extra', api=1, instance_id=1)); self.save()
        with self.assertRaisesRegex(ValueError, 'profile/grants changed'): self.validate()

    def test_files_sd_source_rejected(self):
        self.boot['app_capabilities'][0]['image_source'] = dict(path='Apps/file_browser.elf')
        self.old['boot.json'] = c.encoded(self.boot)
        with self.assertRaisesRegex(ValueError, 'internal-only'): self.validate()

    def test_source_hash_change_rejected(self):
        (self.system / 'Apps/file_browser.c').write_bytes(b'changed after build')
        with self.assertRaisesRegex(ValueError, 'source changed'): self.validate()

    def test_source_traversal_rejected(self):
        self.build['source_sha256']['../outside'] = 'a' * 64; self.save()
        with self.assertRaisesRegex(ValueError, 'Unsafe relative path'): self.validate()

    def test_absolute_source_path_rejected(self):
        self.build['source_sha256']['/tmp/outside'] = 'a' * 64; self.save()
        with self.assertRaisesRegex(ValueError, 'Unsafe relative path'): self.validate()

    def test_missing_source_custody_rejected(self):
        self.build['source_sha256'].pop('Apps/file_browser.c'); self.save()
        with self.assertRaisesRegex(ValueError, 'source custody'): self.validate()

    def test_missing_settings_protection_rejected(self):
        self.build['protected_settings']['listing_open_mutation_copy'] = False; self.save()
        with self.assertRaisesRegex(ValueError, 'protected settings'): self.validate()

    def test_shared_settings_activation_rejected(self):
        self.boot['installation']['shared_settings'] = [1, 6]
        self.old['boot.json'] = c.encoded(self.boot)
        with self.assertRaisesRegex(ValueError, 'authority differs'): c.changed_store(self.old, self.artifacts, 'b' * 40)

    def test_app_removal_rejected(self):
        self.boot['app_capabilities'].pop(); self.old['boot.json'] = c.encoded(self.boot)
        with self.assertRaisesRegex(ValueError, 'authority differs'): c.changed_store(self.old, self.artifacts, 'b' * 40)

    def make_archive(self, members):
        path = self.root / 'test.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, mode in members:
                info = zipfile.ZipInfo(name); info.external_attr = mode << 16
                z.writestr(info, b'fixture')
        return path, dict(bytes=path.stat().st_size, sha256=c.sha(path.read_bytes()))

    def test_archive_exact_bytes_accepted(self):
        p, expected = self.make_archive([('store/boot.json', 0o100644)])
        self.assertEqual(c.archive(p, expected), {'store/boot.json': b'fixture'})

    def test_archive_changed_rejected(self):
        p, expected = self.make_archive([('store/boot.json', 0o100644)]); p.write_bytes(p.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'exact delivered archive'): c.archive(p, expected)

    def test_archive_traversal_rejected(self):
        p, expected = self.make_archive([('../outside', 0o100644)])
        with self.assertRaisesRegex(ValueError, 'Unsafe relative path'): c.archive(p, expected)

    def test_archive_symlink_rejected(self):
        p, expected = self.make_archive([('store/link', 0o120777)])
        with self.assertRaisesRegex(ValueError, 'symlinks'): c.archive(p, expected)

    def test_archive_duplicate_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            p, expected = self.make_archive([('store/boot.json', 0o100644)] * 2)
        with self.assertRaisesRegex(ValueError, 'Duplicate'): c.archive(p, expected)

    def test_full_image_native_change_rejected_before_decode(self):
        base = bytes(0x1000000)
        for offset in (0, 0x8000, 0x10000, 0x270000, 0x800000, 0xff0000, 0xff4000, 0xffffff):
            with self.subTest(offset=hex(offset)):
                modified = bytearray(base); modified[offset] = 1
                with self.assertRaisesRegex(ValueError, 'Unrelated flash bytes'):
                    c.verify_image(bytes(modified), base, {}, {}, {}, None, None)

    def test_full_image_length_rejected(self):
        with self.assertRaisesRegex(ValueError, '16 MiB'):
            c.verify_image(b'', b'', {}, {}, {}, None, None)


if __name__ == '__main__':
    unittest.main()
