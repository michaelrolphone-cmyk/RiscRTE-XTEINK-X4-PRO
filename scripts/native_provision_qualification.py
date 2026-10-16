"""Production-source store admission and offline inactive-bank fault models.

These models never execute Xtensa instructions or operate a physical device.
They do not establish compatibility of an SDK6 app with a deployed bootloader.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

SD_ELF_TIMEOUT_SECONDS = 300


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new):
    require(text.count(old) == 1, 'Admission fixture source anchor changed: ' + old)
    return text.replace(old, new, 1)


def x4_fixture(source, product, sdk):
    source = '#include "experimental/native_replica/NativeAtomicKeyValue.h"\n' + source
    source = replace_once(source, 'bool bind(RiscBoot::Runtime& runtime) {', '''using RC=RiscExperimental::NativeReplicaCore;
using AE=RiscExperimental::NativeAtomicKeyValue;
static RC core1(1,{}, {}, {}),core6(6,{}, {}, {});
static AE endpoint1(core1,{nullptr,[](void*){return true;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return -1;}});
static AE endpoint6(core6,{nullptr,[](void*){return true;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return false;},[](void*){++storageCalls;return -1;}});
bool bind(RiscBoot::Runtime& runtime) {
 struct Writer {const char* app;uint32_t ns;};
 static const Writer writers[]={RISC_NATIVE_SETTINGS_WRITERS};
 for(const auto& writer:writers)if(!runtime.registerAtomicKeyValue(writer.app,writer.ns,writer.ns==6?endpoint6:endpoint1))return false;
 for(uint32_t ns:{1u,6u})if(!runtime.registerAtomicKeyValueReadThrough(ns,ns==6?endpoint6:endpoint1)||!runtime.registerKeyValueAvailability(ns,{nullptr,[](void*,uint32_t,risc_key_value_availability_state_v1*)->int32_t{++storageCalls;return RISC_KEY_VALUE_IO;}}))return false;
''')
    source = replace_once(source, '  RiscCpu::Hardware h{};', '''  RiscCpu::Hardware h{};
 static RiscStorage::Worker mailbox;
 static RiscCpu::StorageWorkBackend worker{&mailbox,[](){return true;},[](){return false;},[](uint32_t){++hardwareCalls;}};h.storageWork=&worker;
 h.sdmmcOpen=[](uint8_t,uint8_t,uint8_t,uint32_t,risc_sdmmc_card_info_v1*){++hardwareCalls;return false;};
 h.sdmmcRead=[](uint64_t,uint32_t,void*){++hardwareCalls;return false;};h.sdmmcWrite=[](uint64_t,uint32_t,const void*){++hardwareCalls;return false;};h.sdmmcSync=[](){++hardwareCalls;return false;};h.sdmmcClose=[](){++hardwareCalls;return false;};
''')
    source = replace_once(source, 'const RiscBoot::KeyValueBackend kv{', 'RiscBoot::KeyValueBackend kv{')
    source = replace_once(source, '  RiscCpu::Port port(hardware());', """  // Released X4 installation.settings_sd requires the existing journal API.
  // Presence only: every I/O callback is counted and must remain uncalled.
  kv.journalRead=[](void*,uint32_t,void*,uint32_t,uint32_t*)->int32_t{++storageCalls;return RISC_KEY_VALUE_IO;};
  kv.journalWrite=[](void*,uint32_t,const void*,uint32_t)->int32_t{++storageCalls;return RISC_KEY_VALUE_IO;};
  kv.legacyNamespace=[](void*,uint32_t,bool*)->int32_t{++storageCalls;return RISC_KEY_VALUE_IO;};
  RiscCpu::Port port(hardware());""")
    source = '#include <RiscProvisionRequestV1.h>\n#include <RiscInternalPackageVolumeV1.h>\n' + source
    source = replace_once(source, '  if (!cpu->bind(runtime)) return false;',
        '  if (!cpu->bind(runtime)) return false;\n' + (product / 'tests/native_provision_admission_fixture.inc').read_text())
    return source


def admit_product(sources, native, before, after, native_proof, sanitized=False):
    import check_runtime_store_admission as admission
    helper_source = (sources['image_helper'] / 'scripts/check_runtime_store_admission.py').read_text()
    import verify_update_elf as verify
    runtime, product, helper = (sources[n] for n in ('runtime', 'product', 'image_helper'))
    contract = json.loads((product / 'docs/native-provision-123/released-baseline.json').read_bytes())
    old_root, old_composition, old_header = admission.ROOT, admission.native_composition, verify.cohort_admission_header
    old_run, old_sanitize = subprocess.run, os.environ.get('SANITIZE')
    require(native_proof.get('file_source_enabled') is False, 'X4 host admission requires the final native file-source selection')
    commands = []
    def composition(selected_runtime, elf, profile, rows):
        require(Path(selected_runtime) == runtime and elf == native and rows == 32 and
                Path(profile) == product / 'profiles/native-provision-123.cmake', 'Wrong native host composition')
        return dict(bounds={'RISC_INSTALLED_APP_CAPACITY': 64, 'RISC_PROVIDER_CAPACITY': 40,
                            'RISC_APP_POLICY_ROWS': 32, 'RISC_APP_REQUIREMENT_ROWS': 24},
                    store_abi=2, file_source_enabled=False, runtime_commit=run_head(runtime),
                    native_layout=native_proof['native_layout'], product_profile_sha256=sha(Path(profile).read_bytes()))
    def header(*args, **kwargs):
        generated = old_header(*args, **kwargs)
        if 'RiscPlatform::millis()' in generated:
            generated = replace_once(generated, 'static uint32_t millis(){return ticks;}',
                                     'namespace RiscPlatform { static uint32_t millis(){return ticks;} }')
        return generated
    def run(command, *args, **kwargs):
        if isinstance(command, list) and command and command[0] in ('c++', 'cc'):
            command = [command[0], '-DRISC_NATIVE_ESP_IDF=1', *command[1:]]
            if command[0] == 'c++' and contract['product'] == 'x4':
                command = [command[0], '-DRISC_RUNTIME_ATOMIC_KEY_VALUE=1', '-include',
                           str(product / 'profiles/native-idf61-settings.h'), '-I' + str(runtime), '-I' + str(runtime / 'test/native_nvs_shim'),
                           '-Wno-unused-function', '-Wno-unused-but-set-variable', *command[1:]]
            commands.append([str(x) for x in command])
        return old_run(command, *args, **kwargs)
    try:
        os.environ['SANITIZE'] = '1' if sanitized else '0'
        os.environ.setdefault('ASAN_OPTIONS', 'detect_leaks=0')
        admission.native_composition, verify.cohort_admission_header, subprocess.run = composition, header, run
        with tempfile.TemporaryDirectory(prefix='native-idf61-admission-') as tmp:
            root = Path(tmp)
            (root / 'tests').mkdir()
            source = (helper / 'tests/runtime_store_admission.cpp').read_text()
            if contract['product'] == 'x4':
                source = x4_fixture(source, product, sources['sdk'])
            (root / 'tests/runtime_store_admission.cpp').write_text(source)
            shutil.copyfile(helper / 'tests/app_data_admission_backend.h', root / 'tests/app_data_admission_backend.h')
            admission.ROOT = root
            result = admission.admit_cohort(runtime, native, before, after, app_policy_rows=32,
                                            native_profile=product / 'profiles/native-provision-123.cmake')
            result.update(sanitized=sanitized, fixture_sha256=sha(source.encode()), helper_adapter_sha256=sha(helper_source.encode()),
                          hardware_calls=0, storage_calls=0, target_instructions_executed=False)
            require(result['elf_count'] == contract['elf_count'], 'Released ELF inventory not completely admitted')
            return result
    finally:
        admission.ROOT, admission.native_composition, verify.cohort_admission_header = old_root, old_composition, old_header
        subprocess.run = old_run
        if old_sanitize is None:
            os.environ.pop('SANITIZE', None)
        else:
            os.environ['SANITIZE'] = old_sanitize


def run_head(root):
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


def preservation_model(baseline, candidate, digest):
    from prepare_preserving_update import layout, pair, plan, selection, ota
    from paired_bank_images import record
    geometry = layout(baseline)
    expanded, natives, stores, size = geometry
    require(not expanded and size == 0x510000, 'Wrong preservation layout')
    _, old_fw, old_store = pair(baseline, 0, geometry)
    _, firmware, store = pair(candidate, 0, geometry)
    cases = []
    def active(image):
        rows = [row for i in range(2) if (row := ota(image[0xff0000+i*4096:0xff0020+i*4096]))]
        return (max(rows)[0] - 1) % 2
    def protected(before, after, ranges):
        require(all(before[start:end] == after[start:end] for start, end in ranges), 'Protected preservation range changed')
    def rejected(snapshot, target=candidate, baseline_digest=digest):
        try:
            plan(snapshot, baseline, target, baseline_digest)
        except ValueError:
            return
        raise ValueError('Unsafe preserving plan accepted')
    for bank in (0, 1):
        for sector in (0, 1):
            for both_valid in (False, True):
                snapshot = bytearray(baseline)
                snapshot[natives[bank]:natives[bank]+len(old_fw)] = old_fw
                snapshot[stores[bank]:stores[bank]+size] = old_store
                snapshot[0xff2000+bank*4096:0xff3000+bank*4096] = record(bank, old_fw, old_store, True, expanded) + b'\xff'*(4096-96)
                sequence = bank + 3
                offset = 0xff0000 + sector*4096
                snapshot[0xff0000:0xff2000] = b'\xff'*8192
                snapshot[offset:offset+4096] = selection(sequence, 2)
                if both_valid:
                    older = 0xff0000 + (1-sector)*4096
                    snapshot[older:older+4096] = selection(sequence-1, 2)
                snapshot[0x9000:0xf000] = bytes(range(256))*96
                snapshot[0x270000:0x2f0000] = bytes(reversed(range(256)))*2048
                snapshot[0xa60000:0xae0000] = bytes(range(256))*2048
                snapshot[0xff4000:] = b'\x91'*(0x1000000-0xff4000)
                rows, receipt = plan(snapshot, baseline, candidate, digest)
                receipt['preserved_ranges'].append((0xa60000, 0xae0000))
                require([row[0] for row in rows] == ['firmware.bin', 'store.bin', 'bank-state.bin', 'ota-selection-LAST.bin'], 'Selection must be last')
                require(receipt['target_bank'] == 1-bank, 'Active bank would be overwritten')
                for index in range(3):
                    name, at, data = rows[index]
                    for cut in (0, 1, len(data)//2, len(data)-1, len(data)):
                        partial = bytearray(snapshot)
                        for _, previous, payload in rows[:index]:
                            partial[previous:previous+len(payload)] = payload
                        erased = (len(data)+4095)//4096*4096
                        partial[at:at+erased] = b'\xff'*erased
                        partial[at:at+cut] = data[:cut]
                        protected(snapshot, partial, receipt['preserved_ranges'])
                        require(active(partial) == bank, 'Torn payload changed active selector')
                        pair(partial, bank, geometry)
                        cases.append('inactive-payload-torn')
                ready = bytearray(snapshot)
                for _, at, data in rows[:3]:
                    ready[at:at+len(data)] = data
                _, at, data = rows[-1]
                for cut in range(33):
                    partial = bytearray(ready)
                    partial[at:at+4096] = b'\xff'*4096
                    partial[at:at+cut] = data[:cut]
                    protected(snapshot, partial, receipt['preserved_ranges'])
                    selected = active(partial)
                    require(selected == (1-bank if cut == 32 else bank), 'Torn selection changed prior to complete CRC record')
                    pair(partial, selected, geometry)
                    cases.append('selection-torn')
                for fault in ('active-native', 'active-store', 'active-state', 'not-confirmed', 'equal-sequence', 'sequence-limit', 'bootloader', 'partition', 'digest'):
                    bad = bytearray(snapshot)
                    at = {'active-native': natives[bank], 'active-store': stores[bank], 'active-state': 0xff2000+bank*4096,
                          'bootloader': 0, 'partition': 0x8000}.get(fault)
                    if at is not None:
                        bad[at] ^= 1
                    elif fault == 'not-confirmed':
                        bad[offset:offset+4096] = selection(sequence, 0)
                    elif fault == 'equal-sequence':
                        bad[0xff0000:0xff2000] = selection(sequence, 2)*2
                    elif fault == 'sequence-limit':
                        bad[offset:offset+4096] = selection(0xfffffffe, 2)
                    rejected(bad, baseline_digest='0'*64 if fault == 'digest' else digest)
                    cases.append('rejected-' + fault)
                for at in (0, 0x8000, 0x10000, 0x2f0000, 0xff2000):
                    bad = bytearray(candidate)
                    bad[at] ^= 1
                    rejected(snapshot, target=bad)
                    cases.append('candidate-corruption')
                ready[rows[-1][1]:rows[-1][1]+len(rows[-1][2])] = rows[-1][2]
                protected(snapshot, ready, receipt['preserved_ranges'])
                require(pair(ready, 1-bank, geometry)[1:] == (firmware, store), 'Selected native/store pair differs')
    return dict(passed=True, cases=len(cases), both_active_banks=True, both_selector_sectors=True,
                fresh_exact_baseline_readback_required=True, nvs_and_appdata_preserved=True,
                unassigned_gap_and_trailing_flash_preserved=True,
                separate_selection_written_last=True, target_instructions_executed=False,
                bootloader_compatibility_tested=False, hardware_tested=False)


def admit_sd(sources, native, files, contract, sanitized=False):
    """Production role/import policy on every retained external ELF, without I/O."""
    import io
    from elftools.elf.elffile import ELFFile
    from verify_update_elf import cohort_admission_header, public_exports
    from native_idf61_provenance import local_module
    imports = local_module(sources['product'], 'native_idf61_candidate.py', 'x4_local_candidate').imports
    runtime = sources['runtime']
    exports = public_exports(ELFFile(io.BytesIO(native)))
    header = cohort_admission_header(runtime, native, store_abi=2)
    header = replace_once(header, 'static bool operationSafe(){return true;}',
                          'static bool safe=true; static const char* missing=nullptr;\nstatic bool operationSafe(){return safe;}')
    header = replace_once(header, 'static uintptr_t elf_find_sym_default(const char* name){',
                          'static uintptr_t elf_find_sym_default(const char* name){\n if(missing&&!strcmp(name,missing))return 0;')
    if 'RiscPlatform::millis()' in header:
        header = replace_once(header, 'static uint32_t millis(){return ticks;}',
                              'namespace RiscPlatform { static uint32_t millis(){return ticks;} }')
    fixture = (sources['product'] / 'minimal/recovery-107/fixtures/strict.cpp').read_bytes()
    results = []
    with tempfile.TemporaryDirectory(prefix='x4-native-sd-admission-') as tmp:
        root = Path(tmp)
        (root / 'cohort_elf_admission.h').write_text(header)
        (root / 'strict.cpp').write_bytes(fixture)
        includes = [runtime / p for p in ('src', 'sdk/app', 'sdk/driver', 'sdk/hardware',
                    'lib/ArduinoJson/src', 'test/drivers/stubs', 'lib/elf_loader/include', 'test/native_bank_stubs')]
        common = ['-DRISC_NATIVE_ESP_IDF=1', *['-I' + str(p) for p in [*includes, root, runtime]]]
        sanitizer = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-no-pie'] if sanitized else []
        subprocess.run(['cc', '-std=c11', *common, *sanitizer, '-c', str(runtime / 'lib/elf_loader/src/esp_elf_validate.c'), '-o', str(root / 'validate.o')], check=True)
        subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-missing-field-initializers',
                        '-Wno-misleading-indentation', *common, *sanitizer, str(root / 'strict.cpp'), str(root / 'validate.o'), '-o', str(root / 'strict')], check=True)
        for name, data in sorted(files.items()):
            if not name.endswith('.elf'):
                continue
            symbols = imports(data)
            require(symbols <= exports.keys(), 'SD import missing from exact native public exports: ' + name + ': ' + str(sorted(symbols - exports.keys())))
            role = contract['sd']['files'][name]['role']
            require(role in ('application', 'driver'), 'Unclassified SD executable')
            image = root / 'candidate.elf'
            image.write_bytes(data)
            environment = {**os.environ, 'ASAN_OPTIONS': os.environ.get('ASAN_OPTIONS', 'detect_leaks=0')}
            started = time.monotonic()
            subprocess.run([str(root / 'strict'), 'app' if role == 'application' else 'driver', str(image), *sorted(symbols)],
                           check=True, timeout=SD_ELF_TIMEOUT_SECONDS, capture_output=True, env=environment)
            require(image.read_bytes() == data, 'SD admission changed payload')
            results.append(dict(path=name, sha256=sha(data), elapsed_seconds=round(time.monotonic()-started, 6), role=role, imports=sorted(symbols),
                                compiled_public_exports={key: hex(exports[key]) for key in sorted(symbols)},
                                strict_admission=True, wrong_role_rejected=True, unsafe_operation_rejected=True,
                                each_missing_import_rejected=True))
    require(len(results) == contract['sd']['elf_count'] == 49, 'Incomplete released SD admission')
    return dict(elf_count=len(results), native_elf_sha256=sha(native), sanitized=sanitized,
                per_elf_timeout_seconds=SD_ELF_TIMEOUT_SECONDS,
                production_header_sha256=sha(header.encode()), strict_fixture_sha256=sha(fixture),
                results=results, device_msc_provider_retained=True, target_instructions_executed=False,
                hardware_tested=False)
