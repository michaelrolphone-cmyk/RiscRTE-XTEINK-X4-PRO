#!/usr/bin/env python3
"""Offline .123 delta/immutability controls; never native target qualification."""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_provision_payloads as p
import native_provision_candidate as candidate
import native_provision_serial as serial

BASELINE = RUNTIME = HELPER = None


def fixture():
    if BASELINE:
        sys.path.insert(0, str(RUNTIME / 'scripts'))
        from spiffs_image import read_image
        raw = BASELINE.read_bytes()
        contract = json.loads(candidate.CONTRACT.read_bytes())
        assert p.sha(raw) == contract['factory_sha256']
        return read_image(raw[0x2f0000:0x800000], 0x510000)
    home = {'version': '0.4.19', 'id': 'paper_clock', 'requires': [{'capability': 'storage.key-value', 'api': 1}]}
    service = {'version': '0.9.0', 'id': 'installed-apps', 'requires': [{'capability': 'platform.installation', 'api': 1}]}
    boot = {'app_capabilities': [{'manifest': 'default.json', 'grants': [
                {'capability': 'retained.' + str(i), 'api': 1, 'instance_id': i} for i in range(24)]}],
            'drivers': [{'manifest': 'installed-apps/manifest.json', 'image_source': {
                'volume_instance': 9, 'internal_fallback': True, 'path': 'Drivers/installed-apps/image-old.elf'}}],
            'installation': {'settings_sd': True, 'volume_instance': 9}}
    return {**{n: p.encoded(v) for n, v in [('default.json', home), ('installed-apps/manifest.json', service),
                                          ('boot.json', boot), ('cohort.json', {'version': '0.1.122'})]},
            'default.elf': b'old home', 'installed-apps/driver.elf': b'old service',
            'settings.elf': b'retained settings', 'settings.json': b'{"version":"1.3.29"}',
            'unrelated.user': b'preserve unrelated'}


def prepared():
    before = fixture()
    home = json.loads(before['default.json']); home['version'] = '0.4.20'; home['requires'].reverse()
    service = json.loads(before['installed-apps/manifest.json']); service['version'] = '0.15.0'
    service['requires'] += [{'capability': 'platform.provision-request', 'api': 1},
                            {'capability': 'platform.package-volume', 'api': 1}]
    packages = {'default.elf': b'new home', 'default.json': p.encoded(home),
                'installed-apps/driver.elf': b'new service', 'installed-apps/manifest.json': p.encoded(service)}
    lock = {'sources': {'product': {'revision': 'a' * 40}}}
    firmware = b'RISC_RUNTIME_VERSION:0.4.7\0new native'
    return before, packages, firmware, lock


def startup_receipt(runtime, sanitized=False):
    """Synthetic validator input, never an execution/qualification receipt."""
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all'] if sanitized else []
    commands = [['c++', '-fsyntax-only', '/temporary/config.cpp'] for _ in range(10)]
    commands.append(['cc', *flags, str(runtime / 'test/fixtures/atomic_key_value_app.c'), '-o', '/temporary/default.elf'])
    commands += [['c++', *flags, '-c', str(runtime / name), '-o', '/temporary/' + Path(name).stem + '.o']
                 for name in serial.OBJECT_SOURCES]
    for provider, instance in [('sdmmc-fatfs', 12), ('x4pro-sd', 9)]:
        commands.append(['cc', *flags, str(runtime / 'test/native_serial_product_provider.c'), '-o', '/temporary/provider.elf'])
        selectors = [] if instance == 12 else ['-DRISC_NATIVE_SERIAL_SD_PROVIDER="x4pro-sd"', '-DRISC_NATIVE_SERIAL_SD_INSTANCE=9']
        commands.append(['c++', *flags, '-DRISC_NATIVE_SERIAL_FILES=1', '-DRISC_NATIVE_SERIAL_SD=1',
                         '-DRISC_NATIVE_ESP_IDF=1', *selectors, '-DTEST_PRODUCT_PROVIDER="' + provider + '"',
                         '-DTEST_PRODUCT_INSTANCE=' + str(instance),
                         str(runtime / 'src/ports/esp32s3/NativeSerialStorage.cpp'),
                         str(runtime / 'test/native_serial_product_storage_test.cpp'), '-o', '/temporary/test'])
        commands += [['/temporary/test', '/temporary', case] for case in serial.CASES]
    return {'profiles': serial.PROFILES[:], 'cases': serial.CASES[:], 'commands': commands,
            'sanitized': sanitized, 'invalid_configurations': 10,
            'limits': 'Host only; no X4 driver or physical device qualification.'}


class Controls(unittest.TestCase):
    def test_factory_self_admission_and_preserving_rejection(self):
        import native_provision_qualification as q
        store_digest = lambda files: p.sha(p.encoded({name: p.sha(data) for name, data in files.items()}))
        grant = {'capability': 'storage.key-value', 'api': 1, 'instance_id': 6}
        boot = {'app_capabilities': [{'manifest': 'default.json', 'grants': []},
                                    {'manifest': 'other.json', 'grants': [grant]}]}
        before = {'boot.json': p.encoded(boot), 'default.elf': b'old ELF'}
        boot['app_capabilities'][0]['grants'].append(grant)
        after = {'boot.json': p.encoded(boot), 'default.elf': b'new ELF'}
        for fault in (None, 'negative-accepted', 'negative-elf', 'negative-io',
                      'control-rejected', 'factory-digest', 'factory-incomplete'):
            calls = []
            def admit(active, candidate, expected):
                index = len(calls); calls.append((active, candidate, expected))
                result = dict(prepared=True, cohort_validated=expected,
                              elf_count=43 if expected else 0, hardware_calls=0, storage_calls=0,
                              active_store_sha256=store_digest(active), candidate_store_sha256=store_digest(candidate))
                if index == 0:
                    if fault == 'negative-accepted': result['cohort_validated'] = True
                    if fault == 'negative-elf': result['elf_count'] = 1
                    if fault == 'negative-io': result['storage_calls'] = 1
                if index == 1 and fault == 'control-rejected': result['cohort_validated'] = False
                if index == 2:
                    if fault == 'factory-digest': result['active_store_sha256'] = '0' * 64
                    if fault == 'factory-incomplete': result['elf_count'] = 42
                return result
            if fault:
                with self.assertRaises(ValueError): q.factory_admission(admit, before, after, 43, store_digest)
            else:
                result = q.factory_admission(admit, before, after, 43, store_digest)
                self.assertEqual(result['mode'], 'factory-bootstrap-self-admission')
                self.assertTrue(result['preserving_transition']['expected_rejection'])
                self.assertFalse(result['preserving_transition']['control_packaged'])
                self.assertEqual([call[2] for call in calls], [False, True, True])
                self.assertEqual(calls[2][:2], (after, after))
                self.assertEqual(json.loads(calls[1][1]['boot.json'])['app_capabilities'][0]['grants'], [])
                self.assertEqual(json.loads(after['boot.json'])['app_capabilities'][0]['grants'], [grant])

    def test_all_linked_owner_workspaces_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); tool = root / 'test/prove_native_serial_workspace.py'
            tool.parent.mkdir(); tool.write_text('synthetic source identity')
            lock = {'native_files': {'firmware_elf': {'path': 'firmware.elf'}}}
            (root / 'firmware.elf').write_bytes(b'fixture ELF')
            names = ('endpoint', 'provider', 'sessions', 'provision')
            for missing in (None, *names):
                output = ''.join('Serial ' + name + ': PASS\n' for name in names if name != missing).encode()
                with mock.patch.object(serial, 'verify_receipts', return_value={'selection': {}}), \
                     mock.patch.object(candidate, 'run', return_value=output) as run:
                    call = lambda: candidate.verify_serial({'runtime': root}, root,
                        Path('/tools/xtensa-esp-elf-gcc'), lock, {'firmware_elf': b'fixture ELF'})
                    if missing:
                        with self.assertRaises(ValueError): call()
                    else:
                        self.assertFalse(call()['hardware_tested'])
                    args = list(run.call_args.args)
                    for name in names:
                        self.assertIn(['--workspace', name], [args[i:i+2] for i in range(len(args)-1)])

    def test_linked_platform_capacity_marker(self):
        from elftools.elf.elffile import ELFFile
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for capacity in (32, 40):
                source = root / 'marker.c'; obj = root / 'marker.o'
                source.write_text('const char risc_platform_capacity[]="RISC_PLATFORM_CAPACITY:' + str(capacity) + '";\n')
                subprocess.run(['cc', '-c', str(source), '-o', str(obj)], check=True)
                elf = ELFFile(io.BytesIO(obj.read_bytes()))
                if capacity == 40:
                    self.assertEqual(candidate.verify_platform_capacity(elf)['value'], 40)
                else:
                    with self.assertRaises(ValueError): candidate.verify_platform_capacity(elf)

    def test_retained_sd_graph_receipt_requires_exact_bytes_and_no_io(self):
        import native_provision_qualification as q
        before = {'sd/driver.elf': b'retained target ELF',
                  'sd/manifest.json': p.encoded({'id': 'x4pro-sd', 'version': '0.2.23',
                      'provides': [{'capability': 'storage.volume', 'api': 1}]}),
                  'boot.json': p.encoded({'drivers': [{'manifest': 'sd/manifest.json', 'instance_id': 9}]})}
        result = {'retained_sd_serial_graph_bound': True, 'hardware_calls': 0, 'storage_calls': 0,
                  'platform_count': 34, 'bound_platform_count': 32,
                  'runtime_owned_platforms': [{'capability': name, 'api': 1, 'scope': 0, 'instance': 0}
                      for name in ('platform.realtime', 'platform.installation')]}
        proof = q.retained_sd_receipt(before, before, result)
        self.assertTrue(proof['production_graph_binding_passed'])
        self.assertFalse(proof['provider_activated'])
        self.assertFalse(proof['target_instructions_executed'])
        for changed in (dict(result, retained_sd_serial_graph_bound=False),
                        dict(result, hardware_calls=1), dict(result, storage_calls=1),
                        dict(result, platform_count=33), dict(result, bound_platform_count=31),
                        dict(result, runtime_owned_platforms=[])):
            with self.assertRaises(ValueError): q.retained_sd_receipt(before, before, changed)
        for name in ('sd/driver.elf', 'sd/manifest.json'):
            with self.assertRaises(ValueError): q.retained_sd_receipt(before, dict(before, **{name: b'changed'}), result)
        changed = dict(before, **{'boot.json': p.encoded({'drivers': [{'manifest': 'sd/manifest.json', 'instance_id': 12}]})})
        with self.assertRaises(ValueError): q.retained_sd_receipt(before, changed, result)

    def test_serial_product_receipt_validation(self):
        for sanitized in (False, True):
            self.assertEqual(serial.validate_receipt(startup_receipt(Path('/runtime'), sanitized), Path('/runtime'), sanitized),
                             {'sd_provider': 'x4pro-sd', 'sd_provider_instance': 9, 'sd_wire_namespace': 12})

    def test_serial_product_receipt_missing_wrong_or_incomplete(self):
        for mutate in (lambda r: r['profiles'].remove('X4SD9'),
                       lambda r: r['cases'].remove('failed-release'),
                       lambda r: r.update(invalid_configurations=9),
                       lambda r: r.update(sanitized=True),
                       lambda r: r['commands'].pop(),
                       lambda r: r['commands'][-1].__setitem__(-1, 'healthy'),
                       lambda r: r['commands'][36].remove('-DRISC_NATIVE_SERIAL_SD_INSTANCE=9'),
                       lambda r: r['commands'][11].__setitem__(2, '/other/src/bootstrap/Json.cpp')):
            receipt = startup_receipt(Path('/runtime'))
            mutate(receipt)
            with self.assertRaises(ValueError): serial.validate_receipt(receipt, Path('/runtime'), False)
        with self.assertRaises(ValueError): serial.verify_receipts({}, {})

    def test_serial_product_sanitizers_required_in_commands(self):
        receipt = startup_receipt(Path('/runtime'), True)
        receipt['commands'][36].remove('-fsanitize=address,undefined')
        with self.assertRaises(ValueError): serial.validate_receipt(receipt, Path('/runtime'), True)

    def test_serial_product_hash_lock_rejects_changed_receipts_and_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / 'runtime'
            for name in serial.SOURCE_FILES:
                path = runtime / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('pinned test source\n')
            paths = [root / (mode + '.json') for mode in ('normal', 'sanitized')]
            for path, sanitized in zip(paths, (False, True)):
                path.write_bytes(p.encoded(startup_receipt(runtime, sanitized)))
            identity = {'revision': 'a' * 40, 'tree': 'b' * 40, 'submodules': []}
            with mock.patch.object(candidate, 'git', return_value=b'a' * 40), mock.patch.object(candidate, 'clean_source', return_value=identity):
                frozen = serial.read_receipts(runtime, *paths)
                lock = {'sources': {'runtime': identity}, 'serial_product_tests': frozen}
                self.assertEqual(serial.verify_receipts(lock, {'runtime': runtime}), frozen)
                original = paths[0].read_bytes(); paths[0].write_bytes(original + b'\n')
                with self.assertRaises(ValueError): serial.verify_receipts(lock, {'runtime': runtime})
                paths[0].write_bytes(original)
                (runtime / 'src/main.cpp').write_text('different startup\n')
                with self.assertRaises(ValueError): serial.verify_receipts(lock, {'runtime': runtime})
                paths[1].unlink()
                with self.assertRaises(ValueError): serial.read_receipts(runtime, *paths)

    def test_workflow_requires_startup_receipts_and_separate_artifacts(self):
        workflow = (ROOT / '.github/workflows/native-provision-123.yml').read_text()
        self.assertEqual(workflow.count('python test/run_native_serial_product_storage_test.py'), 2)
        for flag in ('--serial-product-normal', '--serial-product-sanitized'):
            self.assertIn(flag, workflow)
        self.assertIn('RECEIPT="$NATIVE_ROOT/serial-product/normal.json" SANITIZE=0', workflow)
        self.assertIn('RECEIPT="$NATIVE_ROOT/serial-product/sanitized.json" SANITIZE=1', workflow)
        for label in ('qualification', 'candidate', 'reproducibility'):
            self.assertIn('name: x4-native-provision-123-' + label + '-${{ env.PRODUCT_SHA }}', workflow)
        small = workflow.split('- name: Upload bounded qualification and startup receipts', 1)[1].split('- name: Upload candidate delivery assets', 1)[0]
        self.assertNotIn('/source-evidence/\n', small)
        self.assertNotIn('/build/\n', small)
        self.assertNotIn('/inputs/\n', small)

    def test_exact_delta(self):
        before, packages, firmware, lock = prepared()
        after = p.compose(before, firmware, lock, packages)
        receipt = p.preservation_receipt(before, after)
        self.assertEqual(set(receipt['changed']), p.CHANGED)
        self.assertEqual(after['settings.elf'], before['settings.elf'])
        self.assertEqual(after['settings.json'], before['settings.json'])
        old = json.loads(before['boot.json']); new = json.loads(after['boot.json'])
        self.assertEqual(new['installation'], old['installation'])
        self.assertEqual(new['app_capabilities'][0]['grants'][:-1], old['app_capabilities'][0]['grants'])
        self.assertEqual(len(new['app_capabilities'][0]['grants']), 25)
        self.assertEqual(len(new['drivers']), len(old['drivers']))

    def test_reject_unrelated_mutations(self):
        before, packages, firmware, lock = prepared()
        after = p.compose(before, firmware, lock, packages)
        for name in before:
            if name in p.CHANGED: continue
            with self.subTest(name=name):
                changed = dict(after); changed[name] += b'corrupt'
                with self.assertRaises(ValueError): p.preservation_receipt(before, changed)

    def test_reject_boot_mutations(self):
        before, packages, firmware, lock = prepared()
        after = p.compose(before, firmware, lock, packages)
        for mutator in (lambda boot: boot['app_capabilities'][0]['grants'].pop(0),
                        lambda boot: boot['installation'].update(settings_sd=False),
                        lambda boot: boot['drivers'][0].update(manifest='changed.json')):
            changed = dict(after); boot = json.loads(changed['boot.json']); mutator(boot)
            changed['boot.json'] = p.encoded(boot)
            with self.assertRaises(ValueError): p.preservation_receipt(before, changed)

    def test_reject_wrong_native_version(self):
        before, packages, firmware, lock = prepared()
        for wrong in (b'0.4.0', b'0.4.6', b'0.4.70'):
            with self.assertRaises(ValueError): p.compose(before, firmware.replace(b'0.4.7', wrong), lock, packages)

    def test_reject_manifest_expansion(self):
        before, packages, firmware, lock = prepared()
        for name in ('default.json', 'installed-apps/manifest.json'):
            changed = dict(packages); manifest = json.loads(changed[name]); manifest['requires'].append({'capability': 'unapproved', 'api': 1})
            changed[name] = p.encoded(manifest)
            with self.assertRaises(ValueError): p.compose(before, firmware, lock, changed)

    def test_reject_wrong_versions(self):
        before, packages, firmware, lock = prepared()
        for name in ('default.json', 'installed-apps/manifest.json'):
            changed = dict(packages); manifest = json.loads(changed[name]); manifest['version'] = '0.0.1'
            changed[name] = p.encoded(manifest)
            with self.assertRaises(ValueError): p.compose(before, firmware, lock, changed)

    def test_reject_missing_extra_files(self):
        before, packages, firmware, lock = prepared()
        after = p.compose(before, firmware, lock, packages)
        for changed in (dict(after, unexpected=b'extra'), {n: v for n, v in after.items() if n != 'settings.elf'}):
            with self.assertRaises(ValueError): p.preservation_receipt(before, changed)

    def test_reject_mismatched_mirror_volume(self):
        before, packages, firmware, lock = prepared()
        boot = json.loads(before['boot.json'])
        row = next(r for r in boot['drivers'] if r['manifest'] == 'installed-apps/manifest.json')
        row['image_source']['volume_instance'] = 12
        before['boot.json'] = p.encoded(boot)
        with self.assertRaises(ValueError): p.compose(before, firmware, lock, packages)

    def test_detached_package_receipt_rejected(self):
        with self.assertRaises(ValueError): p.verify_packages({}, {})

    def test_profile_and_frozen_history(self):
        profile = (ROOT / 'profiles/native-provision-123.cmake').read_text()
        self.assertIn('RISC_NATIVE_PROVISION_REQUEST=1', profile)
        self.assertIn('RISC_NATIVE_SERIAL_FILES=1', profile)
        self.assertIn('RISC_NATIVE_SERIAL_SD_INSTANCE=9', profile)
        self.assertIn('RISC_APP_POLICY_ROWS=32', profile)
        self.assertIn('RISC_PLATFORM_CAPACITY=40', profile)
        self.assertIn('-Wl,-u,risc_platform_capacity', profile)
        self.assertIn('RISC_APP_REQUIREMENT_ROWS=24', profile)
        self.assertIn('RISC_NATIVE_SETTINGS_HEADER "${CMAKE_CURRENT_LIST_DIR}/native-idf61-settings.h"', profile)
        self.assertIn('partitions-native-idf61.csv', profile)
        for name in ('profiles/native-idf61.cmake', 'profiles/native-idf61-settings.h',
                     'profiles/partitions-native-idf61.csv', 'scripts/native_idf61_candidate.py',
                     'scripts/native_idf61_build.py', 'scripts/native_idf61_qualification.py',
                     'release/native-idf61/x4-0.1.122.json', '.github/workflows/native-idf61-release.yml'):
            old = subprocess.check_output(['git', '-C', ROOT, 'show', 'c9ecac4058ead7a82b0f74560ac5b19f0b858b3f:' + name])
            self.assertEqual((ROOT / name).read_bytes(), old, name)

    def test_profile_configuration(self):
        if not shutil.which("cmake"): self.skipTest("CMake unavailable locally; required in CI")
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / 'profile.cmake'
            script.write_text('set(RISC_RUNTIME_ROOT "/runtime")\nset(RISC_SOURCE_SHA "' + 'b' * 40 + '")\n' +
                              'set(RISC_X4_SOURCE_SHA "' + 'a' * 40 + '")\n' +
                              'include("' + str(ROOT / 'profiles/native-provision-123.cmake') + '")\n')
            subprocess.run(['cmake', '-P', script], cwd=temp, check=True, capture_output=True)
            selection = (Path(temp) / 'x4-native-idf61/selection.txt').read_text()
            self.assertIn('RISC_NATIVE_PROVISION_REQUEST=1', selection)
            self.assertIn('sha256:docs/native-provision-123/source-inputs.json=', selection)

    def test_admission_fixture_compiles(self):
        if not (RUNTIME and HELPER): self.skipTest('Runtime/helper paths not supplied')
        import native_provision_qualification as q
        source = q.x4_fixture((HELPER / 'tests/runtime_store_admission.cpp').read_text(), ROOT, Path('/unused-sdk'))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.cpp'; path.write_text(source)
            includes = [RUNTIME, RUNTIME / 'src', RUNTIME / 'sdk/app', RUNTIME / 'sdk/driver',
                        RUNTIME / 'sdk/hardware', RUNTIME / 'lib/ArduinoJson/src', RUNTIME / 'test/drivers/stubs',
                        RUNTIME / 'test/native_nvs_shim', HELPER / 'tests']
            command = ['c++', '-std=c++17', '-fsyntax-only', '-DRISC_NATIVE_ESP_IDF=1',
                       '-DRISC_RUNTIME_ATOMIC_KEY_VALUE=1', '-DRISC_APP_POLICY_ROWS=32',
                       '-DRISC_APP_REQUIREMENT_ROWS=24', '-DSTORE_ADMISSION_APP_DATA',
                       '-DRISC_PAIRED_APP_DATA=1', '-DRISC_PLATFORM_CAPACITY=40', *q.SERIAL_GRAPH_FLAGS,
                       '-include', ROOT / 'profiles/native-idf61-settings.h',
                       *['-I' + str(i) for i in includes], path]
            subprocess.run(list(map(str, command)), check=True)
            # Signature-only callback; actual target ELF admission is CI-gated.
            (Path(temp) / 'cohort_elf_admission.h').write_text(
                'namespace CohortElf { static bool file(void*,const char*,bool){return false;} }\n')
            subprocess.run(list(map(str, [*command, '-DSTORE_ADMISSION_COHORT', '-I' + temp])), check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for n in ('baseline', 'runtime', 'image-helper'): parser.add_argument('--' + n, type=Path)
    args, rest = parser.parse_known_args()
    BASELINE, RUNTIME, HELPER = args.baseline, args.runtime, args.image_helper
    # unittest decorators run at import time; set skip after CLI selection.
    Controls.test_admission_fixture_compiles.__unittest_skip__ = not (RUNTIME and HELPER)
    unittest.main(argv=[sys.argv[0], *rest])
