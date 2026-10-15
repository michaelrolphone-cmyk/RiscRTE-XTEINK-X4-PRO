#!/usr/bin/env python3
"""Fail-closed contract tests; no flashing, publication or Xtensa execution."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_idf61_candidate as recipe
from native_idf61_qualification import preservation_model

PARSER = argparse.ArgumentParser()
PARSER.add_argument('--runtime', type=Path, required=True)
PARSER.add_argument('--image-helper', type=Path, required=True)
PARSER.add_argument('--sdk', type=Path, required=True)
PARSER.add_argument('--baseline', type=Path, required=True)
PARSER.add_argument('--sd-archive', type=Path, required=True)
OPTIONS, REST = PARSER.parse_known_args()
SOURCES = {'product': ROOT, 'runtime': OPTIONS.runtime.resolve(), 'image_helper': OPTIONS.image_helper.resolve(), 'sdk': OPTIONS.sdk.resolve()}
recipe.setup_modules(SOURCES)
CONTRACT = json.loads(recipe.CONTRACT.read_bytes())
BASELINE, OLD_NATIVE, BEFORE = recipe.baseline_bytes(OPTIONS.baseline, CONTRACT, SOURCES)
spec = importlib.util.spec_from_file_location('elf_fixture', OPTIONS.runtime / 'test/make_scoped_provider_elf.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class NativeCandidateContracts(unittest.TestCase):
    def test_detached_build_receipt_and_standalone_qualification_rejected(self):
        from types import SimpleNamespace
        args = SimpleNamespace(native_build=Path('/not-a-build'), compiler=Path('/not-a-compiler'))
        for proof in (None, {}, {'fresh_build': True, 'same_process_qualification': True}):
            with self.subTest(proof=proof), self.assertRaisesRegex(ValueError, 'fresh controlled build'):
                recipe.qualify(args, SOURCES, build_proof=proof)

    def test_product_local_qualification_cannot_be_shadowed(self):
        recipe.setup_modules(SOURCES)
        module = recipe.local_module(ROOT, 'native_idf61_qualification.py', 'test_x4_local_qualification')
        self.assertEqual(Path(module.__file__).resolve(), ROOT / 'scripts/native_idf61_qualification.py')
        self.assertTrue(callable(module.admit_sd))
        self.assertIn('rows == 24', __import__('inspect').getsource(module.admit_product))

    def test_effective_profile_overrides_rejected(self):
        from native_idf61_provenance import compiler_definitions
        expected = {'RISC_PROVIDER_CAPACITY': '40', 'RISC_INSTALLED_APP_CAPACITY': '64'}
        flags = ['cc', '-DRISC_PROVIDER_CAPACITY=40', '-D', 'RISC_INSTALLED_APP_CAPACITY=64']
        self.assertEqual(compiler_definitions(flags, expected), expected)
        for extra in (['-URISC_PROVIDER_CAPACITY'], ['-D', 'RISC_PROVIDER_CAPACITY=1'], ['@/tmp/flags'], ['-Wp,-URISC_PROVIDER_CAPACITY']):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                compiler_definitions(flags + extra, expected)

    def test_locked_response_arguments_are_expanded(self):
        from native_idf61_provenance import expand_response_files, compiler_definitions
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blobs = {'response_cflags': b'-mlongcalls -DRISC_PROVIDER_CAPACITY=40'}
            rows = {'response_cflags': {'path': 'toolchain/cflags'}}
            args = expand_response_files(['cc', '@toolchain/cflags'], root, root, blobs, rows)
            self.assertEqual(compiler_definitions(args, {'RISC_PROVIDER_CAPACITY': '40'})['RISC_PROVIDER_CAPACITY'], '40')
            with self.assertRaisesRegex(ValueError, 'Unpinned'):
                expand_response_files(['@/tmp/unpinned'], root, root, blobs, rows)

    def test_effective_generated_sdk_config_must_match(self):
        from native_idf61_provenance import APP_CONFIG, BOOT_CONFIG, FORBIDDEN_CONFIG, effective_sdkconfig
        import copy
        def header(values):
            return ''.join('#define CONFIG_' + key + ' ' + ('1' if value is True else str(value)) + '\n' for key, value in values.items()).encode()
        blobs = {'sdkconfig': ''.join('CONFIG_' + key + '=' + ('y' if value is True else str(value)) + '\n' for key, value in APP_CONFIG.items()).encode(),
                 'sdkconfig_json': json.dumps(APP_CONFIG).encode(), 'sdkconfig_header': header(APP_CONFIG),
                 'bootloader_sdkconfig': json.dumps(BOOT_CONFIG).encode(), 'bootloader_sdkconfig_header': header(BOOT_CONFIG)}
        effective_sdkconfig(blobs)
        for key in APP_CONFIG:
            mutated = dict(blobs)
            values = dict(APP_CONFIG); values[key] = False if values[key] is True else 123
            mutated['sdkconfig_json'] = json.dumps(values).encode()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Effective app SDK JSON'):
                effective_sdkconfig(mutated)
        for key in FORBIDDEN_CONFIG:
            for where in ('sdkconfig_header', 'bootloader_sdkconfig_header'):
                mutated = dict(blobs); mutated[where] += ('#define CONFIG_' + key + ' 0\n').encode()
                with self.subTest(key=key, where=where), self.assertRaisesRegex(ValueError, 'security'):
                    effective_sdkconfig(mutated)
        mutated = dict(blobs); mutated['sdkconfig_header'] = mutated['sdkconfig_header'].replace(b'#define CONFIG_SPIRAM_MODE_OCT 1', b'#define CONFIG_SPIRAM_MODE_OCT 0')
        with self.assertRaisesRegex(ValueError, 'Effective app SDK header'):
            effective_sdkconfig(mutated)

    def test_complete_sd_and_device_msc_are_retained(self):
        files = recipe.released_sd(OPTIONS.sd_archive, CONTRACT, SOURCES['runtime'])
        self.assertEqual(len(files), 77)
        self.assertEqual(sum(name.endswith('.elf') for name in files), 49)
        self.assertTrue(any(name.startswith('Drivers/usb-device-msc-esp32s3/') for name in files))
        self.assertEqual({name: sorted(recipe.imports(data)) for name, data in files.items() if name.endswith('.elf')}, CONTRACT['sd']['elf_imports'])

    def test_changed_or_missing_sd_package_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'required'):
            recipe.released_sd(None, CONTRACT, SOURCES['runtime'])
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'changed.zip'
            archive.write_bytes(OPTIONS.sd_archive.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'Exact released complete SD'):
                recipe.released_sd(archive, CONTRACT, SOURCES['runtime'])

    def test_sd_consumes_one_validated_byte_snapshot(self):
        raw = OPTIONS.sd_archive.read_bytes()
        files = recipe.released_sd_bytes(raw, CONTRACT, SOURCES['runtime'])
        self.assertEqual(len(files), 77)
        with self.assertRaisesRegex(ValueError, 'Exact released complete SD'):
            recipe.released_sd_bytes(raw + b'changed', CONTRACT, SOURCES['runtime'])
        import inspect
        source = inspect.getsource(recipe.qualify)
        self.assertEqual(source.count('args.sd_archive.read_bytes()'), 1)
        self.assertIn("contract['sd']['filename']: sd_archive", source)

    def test_sd_manifest_inventory_cannot_omit_payloads(self):
        import copy
        contract = copy.deepcopy(CONTRACT)
        contract['sd']['files'].pop(next(iter(contract['sd']['files'])))
        with self.assertRaisesRegex(ValueError, 'inventory differs'):
            recipe.released_sd(OPTIONS.sd_archive, contract, SOURCES['runtime'])

    def test_gpio_selection_is_mandatory_artifact(self):
        self.assertIn('x4_selection', recipe.ARTIFACT_KEYS)
        with self.assertRaisesRegex(ValueError, 'Incomplete native'):
            recipe.checked_artifacts({'native_files': {name: {} for name in recipe.ARTIFACT_KEYS if name != 'x4_selection'}}, Path('.'))

    def test_successor_version_cannot_drift(self):
        with self.assertRaisesRegex(ValueError, '0.1.122'):
            recipe.freeze({}, Path('.'), Path('.'), Path('/unused-does-not-exist-x4-lock'), '0.1.121')

    def test_x4_profile_selection_stays_abi2_and24_rows(self):
        self.assertEqual(CONTRACT['store_abi'], 2)
        self.assertEqual(CONTRACT['store_bytes'], 0x510000)
        profile = (ROOT / 'profiles/native-idf61.cmake').read_text()
        self.assertIn('RISC_APP_POLICY_ROWS=24 RISC_APP_REQUIREMENT_ROWS=24', profile)
        self.assertIn('X4_VERSION=0.1.122-idf61-candidate', profile)
        self.assertNotIn('RISC_PAIRED_APP_DATA_EXPANDED', profile)

    def test_runtime_owned_setup_loop_are_not_arduino(self):
        native = ['app_main', 'setup()', 'loop()', 'ArduinoJson::detail::RamString::typeSortKey']
        self.assertEqual(recipe.arduino_runtime_symbols(native), [])
        for name in ('initArduino()', 'loopTask(void*)', 'initVariant()', 'HardwareSerial::begin()', 'String::concat(char const*)', 'HWCDC::write(unsigned char)'):
            with self.subTest(symbol=name):
                self.assertEqual(recipe.arduino_runtime_symbols([name]), [name])

    def test_exact_baseline_inventory(self):
        self.assertEqual(len(BEFORE), CONTRACT['store_file_count'])
        self.assertEqual(sum(name.endswith('.elf') for name in BEFORE), CONTRACT['elf_count'])
        self.assertEqual(recipe.descriptor(OLD_NATIVE), CONTRACT['app_descriptor'])

    def test_exact_released_factory_required(self):
        changed = bytearray(BASELINE)
        changed[0x270001] ^= 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'different.bin'
            path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'Exact released factory'):
                recipe.baseline_bytes(path, CONTRACT, SOURCES)

    def test_missing_and_hidden_private_imports_rejected(self):
        for name in ('xTaskGetTickCount', 'vPortExitCritical', 'esp_intr_alloc'):
            with self.subTest(name=name):
                for image in (fixture.image([name]), fixture.image(['memcpy'], name)):
                    with self.assertRaisesRegex(ValueError, 'Private OS/CPU'):
                        recipe.reject_private({'private/driver.elf': image}, SOURCES['runtime'])

    def test_ordinary_provider_still_accepted(self):
        image = bytes(fixture.image(['memcpy', 'memmove', 'memset', 'strcmp']))
        result = recipe.reject_private({'ordinary/driver.elf': image}, SOURCES['runtime'])
        self.assertEqual(result['ordinary/driver.elf'], ['memcpy', 'memmove', 'memset', 'strcmp'])

    def test_all_released_payloads_kept(self):
        lock = {'candidate_version': '0.0.0-idf61.0123456789ab', 'sources': {'product': {'revision': 'a'*40}}}
        after = recipe.compose_store(BEFORE, OLD_NATIVE, lock)
        self.assertEqual({name for name in BEFORE if BEFORE[name] != after[name]}, {'cohort.json'})
        for path in ('boot.json', 'board.json', 'default.elf', 'default.json', 'springboard.elf', 'springboard.json'):
            self.assertEqual(BEFORE[path], after[path])

    def test_app_descriptor_required(self):
        with self.assertRaisesRegex(ValueError, 'descriptor'):
            recipe.descriptor(b'\0'*288)

    def test_artifact_corruption_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'test.bin').write_bytes(b'x')
            row = {'path': 'test.bin', 'bytes': 1, 'sha256': recipe.sha(b'x')}
            lock = {'native_files': {key: dict(row) for key in recipe.ARTIFACT_KEYS}}
            recipe.checked_artifacts(lock, root)
            (root / 'test.bin').write_bytes(b'y')
            with self.assertRaisesRegex(ValueError, 'differs from lock'):
                recipe.checked_artifacts(lock, root)
            with self.assertRaisesRegex(ValueError, 'Non-canonical'):
                recipe.safe_path(root, '../test.bin')
            (root / 'symlink').symlink_to('/etc/hosts')
            with self.assertRaisesRegex(ValueError, 'outside build'):
                recipe.safe_path(root, 'symlink')

    def test_incomplete_artifact_lock_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete native'):
            recipe.checked_artifacts({'native_files': {}}, Path('.'))

    def test_mutable_and_dirty_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'immutable'):
            recipe.clean_source(ROOT, 'main')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', root], check=True)
            (root / 'a').write_text('source')
            subprocess.run(['git', '-C', root, 'add', 'a'], check=True)
            subprocess.run(['git', '-C', root, '-c', 'user.name=test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'test'], check=True)
            revision = recipe.git(root, 'rev-parse', 'HEAD').decode().strip()
            recipe.clean_source(root, revision)
            (root / 'a').write_text('mutated')
            with self.assertRaisesRegex(ValueError, 'Dirty source'):
                recipe.clean_source(root, revision)

    def test_factory_and_transition_are_distinct(self):
        from current_bootfs import build
        lock = {'candidate_version': '0.0.0-idf61.0123456789ab', 'sources': {'product': {'revision': 'a'*40}}}
        store, _ = build(recipe.compose_store(BEFORE, OLD_NATIVE, lock), size=0x510000)
        new_bootloader = b'\xaa'*14032
        factory, transition = recipe.make_images(BASELINE, OLD_NATIVE, new_bootloader, store)
        self.assertNotEqual(factory[:0x8000], transition[:0x8000])
        self.assertEqual(transition[:0x10000], BASELINE[:0x10000])
        self.assertEqual(factory[0x9000:0xf000], BASELINE[0x9000:0xf000])
        self.assertEqual(factory[0x270000:0x2f0000], BASELINE[0x270000:0x2f0000])
        from prepare_preserving_update import plan
        with self.assertRaisesRegex(ValueError, 'Bootloader/partition mismatch'):
            plan(BASELINE, BASELINE, factory, CONTRACT['factory_sha256'])
        proof = preservation_model(BASELINE, transition, CONTRACT['factory_sha256'])
        self.assertEqual(proof['cases'], 496)
        self.assertFalse(proof['bootloader_compatibility_tested'])
        self.assertFalse(proof['hardware_tested'])
        self.assertTrue(proof['unassigned_gap_and_trailing_flash_preserved'])

    def test_repeated_packing_is_identical(self):
        from current_bootfs import build
        first, record = build(BEFORE, size=0x510000)
        second, repeated = build(dict(reversed(list(BEFORE.items()))), size=0x510000)
        self.assertEqual(first, second)
        self.assertEqual(record, repeated)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *REST])
