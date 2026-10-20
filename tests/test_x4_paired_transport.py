#!/usr/bin/env python3
"""Host-only complete X4 SD payload roundtrip, never a device or flash installer.

The payload fixture uses namespace 1 on POSIX storage. The separate production
startup suite proves X4 wire namespace 12 -> x4pro-sd instance 9. Neither fixture
executes retained Xtensa ELFs, mounts physical SD, activates packages, or proves
flash sequencing/durability. All temporary build/storage files use tempfile.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PIN = '6a3b3d46f5b2857eacc6e9863799dec1f466b036'
CASES = ['healthy', 'absent-media', 'refresh-refused', 'refresh-retained',
         'failed-close', 'failed-release', 'unadmitted', 'wrong-provider',
         'wrong-instance', 'wrong-api', 'wrong-capability', 'ambiguous', 'invalid-board']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def profile_mapping(text):
    text = '\n'.join(line.split('#', 1)[0] for line in text.splitlines())
    for name in ('FILES', 'BOOT_FILES', 'APPDATA_FILES', 'SD'):
        values = re.findall(r'\bRISC_NATIVE_SERIAL_' + name + r'=([^\s)]+)', text)
        require(values == ['1'], 'Missing/ambiguous serial profile flag: ' + name)
    require(re.findall(r'\bRISC_NATIVE_SERIAL_SD_INSTANCE=([^\s)]+)', text) == ['9'],
            'X4 serial provider instance must be exactly 9, not wire namespace 12')
    require(text.count('RISC_NATIVE_SERIAL_SD_PROVIDER=') == 1 and
            'RISC_NATIVE_SERIAL_SD_PROVIDER=\\"x4pro-sd\\"' in text,
            'X4 serial provider must be exactly x4pro-sd')


def read_payload(path, expected_sha256, expected_files, client):
    require(path.stat().st_size <= 64 * 1024 * 1024, 'SD archive exceeds host bound')
    raw = path.read_bytes()
    require(sha(raw) == expected_sha256, 'SD archive SHA256 mismatch')
    baseline = json.loads((ROOT / 'docs/native-provision-123/released-baseline.json').read_bytes())['sd']
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        require(len(names) == len(set(names)) == expected_files, 'Duplicate/missing/extra SD members')
        require(len({name.casefold() for name in names}) == len(names), 'Case-folded SD path collision')
        require(sum(row.file_size for row in infos) <= 32 * 1024 * 1024, 'SD expansion exceeds bound')
        values = {}
        for row in infos:
            path = PurePosixPath(row.filename)
            mode = stat.S_IFMT(row.external_attr >> 16)
            require(row.orig_filename == row.filename and not row.is_dir() and
                    mode in (0, stat.S_IFREG) and not row.flag_bits & 1 and
                    row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                    0 <= row.file_size <= 4 * 1024 * 1024, 'Invalid SD member type/size')
            require(not path.is_absolute() and str(path) == row.filename and '..' not in path.parts,
                    'Noncanonical SD member')
            client.path_bytes('/' + row.filename)
            values[row.filename] = archive.read(row)
    require(set(baseline['files']) <= set(values), 'Original 77-path payload was not retained')
    for name, expected in baseline['files'].items():
        require(len(values[name]) == expected['bytes'] and sha(values[name]) == expected['sha256'],
                'Original payload changed: ' + name)
    extras = set(values) - set(baseline['files'])
    if expected_files == 77:
        require(not extras and sha(raw) == baseline['sha256'], 'Baseline archive changed')
    else:
        require(len(extras) == 1, 'Candidate must add exactly one catalog-service mirror')
        name = next(iter(extras))
        require(name == 'Drivers/installed-apps/image-' + sha(values[name]) + '.elf' and
                values[name].startswith(b'\x7fELF'), 'Candidate mirror path/content identity mismatch')
    parents = sorted({str(parent) for name in values for parent in PurePosixPath(name).parents
                      if str(parent) != '.'}, key=lambda value: (value.count('/'), value))
    require(not set(values).intersection(parents), 'SD file/directory collision')
    for parent in parents:
        client.path_bytes('/' + parent)
    return values, parents


class Wire:
    """Anonymous pipes only; this class cannot open a serial character device."""
    def __init__(self, root, binary, sf):
        self.process = subprocess.Popen([str(binary), str(root)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self.transport = sf.FDTransport(self.process.stdout.fileno(), self.process.stdin.fileno())
        self.commands = []
        self.drop = None
        self.closed = False

    def write(self, data, deadline):
        self.commands.append(data.split()[3].decode())
        self.transport.write(data, deadline)

    def line(self, deadline):
        result = self.transport.line(deadline)
        if self.drop == self.commands[-1]:
            self.drop = None
            raise TimeoutError('injected lost acknowledgment after endpoint execution')
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.process.stdin.close()
        try:
            status = self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            raise AssertionError('Host wire fixture did not shut down')
        finally:
            self.process.stdout.close()
        errors = self.process.stderr.read().decode(errors='replace')
        self.process.stderr.close()
        require(status == 0 and not errors, 'Host wire fixture failed: ' + errors)


def test_class(sf, binary, payload, parents, profile):
    class PayloadTransport(unittest.TestCase):
        def setUp(self):
            self.temp = tempfile.TemporaryDirectory(prefix='x4-paired-files-')
            self.root = Path(self.temp.name)
            self.addCleanup(self.temp.cleanup)
            self.wire = Wire(self.root, binary, sf)
            self.addCleanup(self.wire.close)
            self.client = sf.Client(self.wire)
            self.sibling = self.root / 'unrelated-user-file.bin'
            self.sibling.write_bytes(b'preserve unrelated user bytes')

        def preserved(self):
            self.assertEqual(self.sibling.read_bytes(), b'preserve unrelated user bytes')

        def test_all_payload_files_roundtrip(self):
            # An already existing directory and unrelated nested content survive.
            (self.root / 'Apps').mkdir()
            (self.root / 'Apps/user-book.txt').write_bytes(b'user content')
            for parent in parents:
                try:
                    info = self.client.stat(1, '/' + parent)
                except sf.RemoteError as error:
                    self.assertEqual(error.code, 1)
                    self.client.mkdir(1, '/' + parent)
                else:
                    self.assertTrue(info.directory)
            for name, data in sorted(payload.items()):
                with self.subTest(path=name):
                    self.client.put_stream(1, '/' + name, io.BytesIO(data), len(data))
                    sink = io.BytesIO()
                    self.assertEqual(self.client.get_stream(1, '/' + name, sink), len(data))
                    self.assertEqual(sink.getvalue(), data)
                    self.assertEqual(self.client.stat(1, '/' + name).size, len(data))
            self.assertEqual((self.root / 'Apps/user-book.txt').read_bytes(), b'user content')
            self.assertEqual({str(path.relative_to(self.root)) for path in self.root.rglob('*') if path.is_file()},
                             set(payload) | {'Apps/user-book.txt', self.sibling.name})
            self.preserved()

        def test_create_is_exclusive_and_mkdir_not_recursive(self):
            (self.root / 'existing').write_bytes(b'original')
            with self.assertRaises(sf.FileTransferError):
                self.client.put_stream(1, '/existing', io.BytesIO(b'new'), 3)
            self.assertEqual((self.root / 'existing').read_bytes(), b'original')
            with self.assertRaises(sf.FileTransferError):
                self.client.put_stream(1, '/absent', io.BytesIO(b'new'), 3, replace=True)
            self.assertFalse((self.root / 'absent').exists())
            with self.assertRaises(sf.RemoteError):
                self.client.mkdir(1, '/missing/child')
            self.assertFalse((self.root / 'missing').exists())
            self.client.mkdir(1, '/directory')
            with self.assertRaises(sf.FileTransferError):
                self.client.put_stream(1, '/directory', io.BytesIO(b'new'), 3, replace=True)
            self.assertTrue((self.root / 'directory').is_dir())
            self.preserved()

        def test_explicit_shorter_and_empty_replace(self):
            target = self.root / 'existing'
            target.write_bytes(b'original longer content')
            for data in (b'new', b''):
                self.client.put_stream(1, '/existing', io.BytesIO(data), len(data), replace=True)
                sink = io.BytesIO()
                self.client.get_stream(1, '/existing', sink)
                self.assertEqual(sink.getvalue(), data)
                self.assertEqual(target.read_bytes(), data)
            self.preserved()

        def test_abort_keeps_partial_create_and_replace(self):
            for replace in (False, True):
                path = '/replace' if replace else '/create'
                target = self.root / path[1:]
                if replace:
                    target.write_bytes(b'original must not be claimed restored')
                self.client._path(1, path)
                self.client._request('PUT', 1, 'replace' if replace else 'create', 100)
                self.assertEqual(target.read_bytes(), b'')
                self.client._request('WRITE', 0, b'partial'.hex())
                self.client.abort()
                self.assertEqual(target.read_bytes(), b'partial')
            self.preserved()

        def test_lost_acknowledgment_has_no_retry_or_rollback(self):
            target = self.root / 'existing'
            target.write_bytes(b'old contents')
            self.wire.drop = 'WRITE'
            with self.assertRaises(sf.FileTransferError):
                self.client.put_stream(1, '/existing', io.BytesIO(b'x' * 96), 96, replace=True)
            self.assertFalse(self.client.usable)
            self.assertEqual(self.wire.commands.count('WRITE'), 1)
            self.assertNotIn('ABORT', self.wire.commands)
            self.assertNotIn('COMMIT', self.wire.commands)
            self.assertEqual(target.read_bytes(), b'x' * 48)
            count = len(self.wire.commands)
            with self.assertRaises(sf.FileTransferError):
                self.client.stat(1, '/existing')
            self.assertEqual(len(self.wire.commands), count)
            self.preserved()

        def test_disconnect_keeps_partial_replacement(self):
            target = self.root / 'existing'
            target.write_bytes(b'old contents must not be claimed restored')
            self.client._path(1, '/existing')
            self.client._request('PUT', 1, 'replace', 100)
            self.client._request('WRITE', 0, b'partial'.hex())
            self.wire.close()  # EOF closes known handles, without undoing writes.
            self.assertEqual(target.read_bytes(), b'partial')
            self.preserved()

        def test_lost_commit_ack_is_not_reported_as_success(self):
            self.wire.drop = 'COMMIT'
            with self.assertRaises(sf.FileTransferError):
                self.client.put_stream(1, '/uncertain', io.BytesIO(b'complete'), 8)
            self.assertFalse(self.client.usable)
            self.assertEqual(self.wire.commands.count('COMMIT'), 1)
            self.assertNotIn('ABORT', self.wire.commands)
            # The test can inspect backing storage; the real client cannot infer
            # this result from a lost acknowledgment and never retries it.
            self.assertEqual((self.root / 'uncertain').read_bytes(), b'complete')
            self.preserved()

        def test_unavailable_readonly_and_wrong_namespace_do_not_fallback(self):
            for namespace in (2, 3, 9, 12):
                with self.subTest(namespace=namespace), self.assertRaises(sf.FileTransferError):
                    self.client.put_stream(namespace, '/not-written', io.BytesIO(b'new'), 3)
                self.assertFalse((self.root / 'not-written').exists())
            self.preserved()

        def test_product_mapping_guard_rejects_mutations(self):
            profile_mapping(profile)
            for wrong in (profile.replace('RISC_NATIVE_SERIAL_SD_INSTANCE=9', 'RISC_NATIVE_SERIAL_SD_INSTANCE=12'),
                          profile.replace('x4pro-sd', 'sdmmc-fatfs'),
                          profile.replace('RISC_NATIVE_SERIAL_SD=1', 'RISC_NATIVE_SERIAL_SD=0')):
                with self.assertRaises(ValueError):
                    profile_mapping(wrong)
    return PayloadTransport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--sd-archive', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--expected-files', type=int, choices=(77, 78), required=True)
    parser.add_argument('--profile', type=Path, default=ROOT / 'profiles/native-paired-124.cmake')
    parser.add_argument('--receipt', '--output', dest='receipt', type=Path, required=True)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    require(__debug__, 'Python assertions must remain enabled in upstream startup tests')
    runtime = args.runtime.resolve()
    revision = subprocess.check_output(['git', '-C', str(runtime), 'rev-parse', 'HEAD'], text=True).strip()
    require(revision == PIN, 'Wrong Runtime revision')
    require(not subprocess.check_output(['git', '-C', str(runtime), 'status', '--porcelain', '--untracked-files=no']),
            'Runtime has tracked changes')
    profile = args.profile.read_text()
    profile_mapping(profile)
    spec = importlib.util.spec_from_file_location('serial_files', runtime / 'scripts/serial_files.py')
    sf = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = sf
    spec.loader.exec_module(sf)
    payload, parents = read_payload(args.sd_archive, args.expected_sha256, args.expected_files, sf)
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONOPTIMIZE': '0',
                   'SANITIZE': '1' if args.sanitize else '0'}
    environment.setdefault('ASAN_OPTIONS', 'detect_leaks=0')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    startup_receipt = args.receipt.with_suffix('.startup.json')
    startup_log = args.receipt.with_suffix('.startup.log')
    require(not any(path.exists() for path in (args.receipt, startup_receipt, startup_log)),
            'Choose unused receipt/output paths; do not overwrite earlier evidence')
    startup_command = [sys.executable, str(runtime / 'test/run_native_serial_product_storage_test.py')]
    with startup_log.open('w') as log:
        subprocess.run(startup_command, check=True, timeout=240, env={**environment, 'RECEIPT': str(startup_receipt)},
                       stdout=log, stderr=subprocess.STDOUT)
    startup = json.loads(startup_receipt.read_bytes())
    require(startup['profiles'] == ['legacyWave12', 'X4SD9'] and startup['cases'] == CASES and
            startup['invalid_configurations'] == 10 and startup['sanitized'] is args.sanitize,
            'Incomplete or wrong-mode actual production startup receipt')
    with tempfile.TemporaryDirectory(prefix='x4-paired-wire-build-') as temporary:
        binary = Path(temporary) / 'wire'
        command = [os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                   '-Wno-missing-field-initializers', '-g', '-no-pie']
        if args.sanitize:
            command += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        command += ['-I' + str(runtime / path) for path in ('src', 'sdk/app', 'sdk/driver')]
        command += [str(runtime / 'src/runtime/serial/Files.cpp'), str(runtime / 'test/serial_files_wire.cpp'),
                    '-o', str(binary)]
        subprocess.run(command, check=True, timeout=120, env=environment)
        # Child fixtures inherit sanitizer settings, with no serial transport use.
        previous = os.environ.get('ASAN_OPTIONS')
        os.environ['ASAN_OPTIONS'] = environment['ASAN_OPTIONS']
        try:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_class(sf, binary, payload, parents, profile))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        finally:
            if previous is None:
                os.environ.pop('ASAN_OPTIONS', None)
            else:
                os.environ['ASAN_OPTIONS'] = previous
        require(result.wasSuccessful(), 'X4 payload transport regression failed')
    require(args.profile.read_text() == profile, 'Product profile changed during the test')
    require(subprocess.check_output(['git', '-C', str(runtime), 'rev-parse', 'HEAD'], text=True).strip() == PIN and
            not subprocess.check_output(['git', '-C', str(runtime), 'status', '--porcelain', '--untracked-files=no']),
            'Runtime source changed during the test')
    source_files = ['scripts/serial_files.py', 'src/runtime/serial/Files.cpp', 'test/serial_files_wire.cpp',
                    'src/runtime/storage/PosixFiles.h', 'src/ports/esp32s3/NativeSerialStorage.cpp',
                    'src/ports/esp32s3/NativeSerialStorage.h', 'src/ports/esp32s3/NativeSerialStorageBinding.h',
                    'test/run_native_serial_product_storage_test.py', 'test/native_serial_product_storage_test.cpp']
    receipt = dict(schema=1, runtime_revision=revision, archive_sha256=args.expected_sha256,
                   file_count=len(payload), directory_count=len(parents), bytes=sum(map(len, payload.values())),
                   sanitized=args.sanitize, tests_run=result.testsRun, full_roundtrip_verified=True,
                   preservation_and_interruption_cases_passed=True, fixture_namespace=1,
                   x4_mapping={'wire_namespace': 12, 'provider': 'x4pro-sd', 'provider_instance': 9},
                   startup_command=startup_command, startup_receipt=startup,
                   startup_log_sha256=sha(startup_log.read_bytes()), fixture_compile_command=command,
                   profile_sha256=sha(args.profile.read_bytes()), test_sha256=sha(Path(__file__).read_bytes()),
                   source_sha256={name: sha((runtime / name).read_bytes()) for name in source_files},
                   files={name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in sorted(payload.items())},
                   hardware_tested=False, consumer_activation_tested=False, flash_sequencing_tested=False,
                   limits='Host Python client and production RTEF1 endpoint over anonymous pipes with POSIX storage. '
                          'Separate production startup/Runtime mapping uses synthetic storage. No retained X4 ELF '
                          'execution, physical SD, device access, package activation, flash or durability claim.')
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(f'PASS: {len(payload)} files / {len(parents)} directories; receipt {args.receipt}')


if __name__ == '__main__':
    main()
