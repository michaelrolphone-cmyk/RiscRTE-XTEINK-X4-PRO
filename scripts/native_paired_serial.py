"""Validate and hash-lock the actual Runtime product startup host receipts.

These are CI host-test evidence, not device evidence or native-build attestation.
The controlled native producer separately requires its in-process build proof.
"""
import hashlib
import json
from pathlib import Path


CASES = ['healthy', 'absent-media', 'refresh-refused', 'refresh-retained',
         'failed-close', 'failed-release', 'unadmitted', 'wrong-provider',
         'wrong-instance', 'wrong-api', 'wrong-capability', 'ambiguous', 'invalid-board']
PROFILES = ['legacyWave12', 'X4SD9']
OBJECT_SOURCES = ['src/bootstrap/Json.cpp', 'src/bootstrap/Board.cpp', 'src/bootstrap/Runtime.cpp',
                  'src/runtime/streams/AppStreamSessions.cpp', 'src/runtime/streams/ProviderQueueHost.cpp',
                  'src/runtime/drivers/ProviderGraphV2.cpp', 'src/runtime/drivers/ProviderModuleV2.cpp',
                  'src/runtime/serial/Files.cpp', 'src/ports/esp32s3/NativeSerialFiles.cpp']
TEST_SCRIPT = 'test/run_native_serial_product_storage_test.py'
SOURCE_FILES = [TEST_SCRIPT, 'src/main.cpp', 'src/ports/esp32s3/NativeSerialStorage.h',
                'src/ports/esp32s3/NativeSerialStorageBinding.h',
                'src/ports/esp32s3/NativeSerialStorage.cpp', 'test/native_serial_product_storage_test.cpp',
                'test/native_serial_product_provider.c', 'test/fixtures/atomic_key_value_app.c', *OBJECT_SOURCES]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_receipt(receipt, runtime, sanitized):
    """Reject incomplete, wrong-profile, wrong-source or unsanitized runs."""
    require(receipt.get('profiles') == PROFILES and receipt.get('cases') == CASES,
            'Incomplete serial product startup profiles/cases')
    require(type(receipt.get('invalid_configurations')) is int and receipt['invalid_configurations'] == 10,
            'Missing serial product invalid-selector coverage')
    require(receipt.get('sanitized') is sanitized, 'Wrong serial product sanitizer receipt')
    require(isinstance(receipt.get('limits'), str) and 'no X4 driver or physical device qualification' in receipt['limits'],
            'Serial product host evidence scope missing')
    commands = receipt.get('commands')
    require(isinstance(commands, list) and len(commands) == 50 and
            all(isinstance(c, list) and c and all(isinstance(a, str) for a in c) for c in commands),
            'Incomplete serial product command evidence')
    require(len([c for c in commands if '-fsyntax-only' in c]) == 10,
            'Missing negative serial product configuration compiles')
    for relative in OBJECT_SOURCES:
        matches = [c for c in commands if '-c' in c and str(runtime / relative) in c]
        require(len(matches) == 1, 'Serial product object source mismatch: ' + relative)
    compiled = [c for c in commands if '-o' in c]
    require(len(compiled) == 14, 'Serial product compile/link inventory mismatch')
    for command in compiled:
        sanitizers = [a for a in command if a.startswith('-fsanitize=')]
        require(sanitizers == (['-fsanitize=address,undefined'] if sanitized else []) and
                ('-fno-sanitize-recover=all' in command) is sanitized,
                'Serial product compiler sanitizer selection mismatch')
    links = [(i, c) for i, c in enumerate(commands)
             if str(runtime / 'src/ports/esp32s3/NativeSerialStorage.cpp') in c]
    require(len(links) == 2, 'Missing production serial startup binding links')
    for (index, command), provider, instance in zip(links, ['sdmmc-fatfs', 'x4pro-sd'], [12, 9]):
        required = {'-DRISC_NATIVE_SERIAL_FILES=1', '-DRISC_NATIVE_SERIAL_SD=1', '-DRISC_NATIVE_ESP_IDF=1',
                    '-DTEST_PRODUCT_PROVIDER="' + provider + '"', '-DTEST_PRODUCT_INSTANCE=' + str(instance),
                    str(runtime / 'test/native_serial_product_storage_test.cpp')}
        require(required <= set(command), 'Serial product startup fixture selection mismatch')
        selectors = [a for a in command if a.startswith(('-DRISC_NATIVE_SERIAL_SD_PROVIDER=', '-DRISC_NATIVE_SERIAL_SD_INSTANCE='))]
        require(selectors == ([] if instance == 12 else ['-DRISC_NATIVE_SERIAL_SD_PROVIDER="x4pro-sd"',
                                                        '-DRISC_NATIVE_SERIAL_SD_INSTANCE=9']),
                'Serial product explicit X4 SD9 binding mismatch')
        require(command.count('-o') == 1 and command.index('-o') + 1 < len(command), 'Missing serial product test executable')
        binary = command[command.index('-o') + 1]
        executed = commands[index + 1:index + 1 + len(CASES)]
        require(executed == [[binary, str(Path(binary).parent), case] for case in CASES],
                'Incomplete executed serial product startup cases')
    return {'sd_provider': 'x4pro-sd', 'sd_provider_instance': 9, 'sd_wire_namespace': 12}


def read_receipts(runtime, normal, sanitized):
    import native_paired_candidate as recipe
    runtime = runtime.resolve()
    paths = {'normal': normal.resolve(), 'sanitized': sanitized.resolve()}
    require(len(set(paths.values())) == 2, 'Serial product receipts must be distinct')
    rows = {}
    selections = []
    for mode, path in paths.items():
        require(path.is_file() and path.stat().st_size <= 1024 * 1024, 'Missing/oversized serial product receipt: ' + str(path))
        raw = path.read_bytes()
        value = json.loads(raw)
        selections.append(validate_receipt(value, runtime, mode == 'sanitized'))
        rows[mode] = {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw), 'receipt': value}
    require(selections[0] == selections[1], 'Serial product test selections differ')
    source = recipe.clean_source(runtime, recipe.git(runtime, 'rev-parse', 'HEAD').decode().strip())
    return {'schema': 1, 'runtime': source,
            'source_files': {name: sha((runtime / name).read_bytes()) for name in SOURCE_FILES},
            'selection': selections[0], 'runs': rows, 'hardware_tested': False}


def verify_receipts(lock, sources):
    frozen = lock.get('serial_product_tests')
    require(isinstance(frozen, dict) and set(frozen.get('runs', {})) == {'normal', 'sanitized'},
            'Final qualification requires both production serial startup receipts')
    require(frozen.get('runtime') == lock['sources']['runtime'], 'Serial startup Runtime pin differs from native build')
    fresh = read_receipts(sources['runtime'], *[Path(frozen['runs'][mode]['path']) for mode in ('normal', 'sanitized')])
    require(fresh == frozen, 'Serial product startup receipts/source changed after freeze')
    return fresh
