#!/usr/bin/env python3
"""Assemble a selected exact X4 BIN plus its qualified NOVA Reader components.

This recovery path observes public resolver tables in the original native BIN,
then runs the unchanged production ELF admission and complete Runtime cohort
on the host. It neither synthesizes a native ELF nor substitutes a new firmware.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

BASE_SHA = 'bd84004903b2bc6d4c843c89f9c4eb76ab89f2b1894e31644c671297c06c8116'
NATIVE_SHA = 'fc1fe5f1286668136156949932605a792c7dea048dc403f3f04d676ded14ab36'
PANEL_SHA = '3fe67b0b8b22b739b4cee6cb5d8e5da9536883ae567b6d61b142de5da50181d4'
SCENE_SHA = 'f63441c1ab72b24db8598fabffe4eb20df889210ca09cf275bafc78ace458787'
READER_SHA = '8ac56cf37fc1669bba9bd0292661cf9ff74327db3f90072e8298bbb14e83f3b2'
RUNTIME_TREE = '03add2558ecd81dce7029af952115841dcaf3de4'
ADMISSION_SHA = '1ae5a6798d0ee019aea1beea9b7f94921d0e9a2cc5e3293fc747b913e370b19d'
IMAGE_NAME = 'X4-0.1.76-Reader-Panel-0.1.12-full-0x0.bin'
ALLOWED = {'ui-scene/driver.elf', 'ui-scene/manifest.json', 'ebook_reader.json', 'cohort.json'}

# Keep the previously delivered 0.1.76 recipe reproducible. New increments select
# the exact tested BIN, not the generic driver workflow's older SDK defaults.
BUILD_SELECTIONS = {
    '0.1.76': {'baseline_version': '0.1.75', 'baseline_sha256': BASE_SHA,
               'scene_version': '0.3.5', 'scene_sha256': SCENE_SHA,
               'reader_version': '0.1.6', 'reader_sha256': READER_SHA},
    '0.1.77': {'baseline_version': '0.1.76',
               'baseline_sha256': '5a00e718132b8381f0e58a8af1f1b40301580ba9d73f164c20561fae98b962c5',
               'scene_version': '0.3.6',
               'scene_sha256': 'fd8543dcb48d02f08cfcda144b0038d457f59b9cc5bf670caeee746f92af3ff7',
               'reader_version': '0.1.8',
               'reader_sha256': '455190996d053b15b79cbad3637386222f3a5286f76016c128f48594801f8bab'},
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def inventory(store):
    return {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(store.items())}


def write_store(root, store):
    for name, data in store.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def imports(raw):
    from elftools.elf.elffile import ELFFile
    elf = ELFFile(io.BytesIO(raw))
    return sorted({s.name for table in elf.iter_sections()
                   if table['sh_type'] in ('SHT_DYNSYM', 'SHT_SYMTAB')
                   for s in table.iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF'})


def native_witness(runtime, raw):
    from native_binary_exports import exports
    resolver = runtime / 'lib/elf_loader/src/esp_elf_symbol.c'
    source = resolver.read_text()
    start = source.index('static const struct esp_elfsym g_esp_libc_elfsyms[]')
    table = source[start:source.index('};', start) + 2]
    bootstrap = (runtime / 'src/bootstrap/Runtime.cpp').read_text()
    require('static const esp_elfsym symbols[]={{"risc_runtime_get_api",reinterpret_cast<const void*>(&risc_runtime_get_api)},ESP_ELFSYM_END};' in bootstrap,
            'Runtime public export source differs')
    matches = []
    for locale in (0, 1):
        text = subprocess.check_output(['cpp', '-P', '-DRISC_APP_IMAGE_CACHE=1',
               '-DCONFIG_LIBC_PICOLIBC=0', '-D__HAVE_LOCALE_INFO__=' + str(locale)], input=table, text=True)
        names = [a or b for a, b in re.findall(r'ESP_ELFSYM_EXPORT\(\s*([a-zA-Z0-9_]+)\s*\)|\{\s*"([a-zA-Z0-9_]+)"', text)]
        try:
            result, proof = exports(raw, {'g_esp_libc_elfsyms': names,
                     '_ZZN8RiscBoot7Runtime3runEvE7symbols': ['risc_runtime_get_api']})
        except ValueError:
            continue
        proof.update(resolver_source_sha256=sha(resolver.read_bytes()), locale_info=locale)
        matches.append((result, proof))
    require(len(matches) == 1, 'Native resolver table does not have one exact source match')
    return matches[0]


def compile_admission(runtime, tools, output, exported, sanitized, sanitizers="address,undefined", installed_catalog=False, shared_files=False):
    from verify_update_elf import extract, admission_source
    text = (runtime / 'src/ports/esp32s3/NativeBankStore.cpp').read_text()
    require(sha(text.encode()) == ADMISSION_SHA, 'Native admission source differs from the qualified baseline')
    roles = admission_source(text)[0]
    prelude = '''#include <cassert>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>
#include "private/elf_types.h"
#include "RiscBankStoreV1.h"
#include "runtime/drivers/NativeProviderPolicyValidationV1.h"
extern "C" bool esp_elf_validate_file(const uint8_t*,size_t);
namespace CohortElf {
static uint32_t ticks=0;static bool safe=true;static const char* missing=nullptr;
static bool operationSafe(){return safe;}
static uint32_t millis(){return ticks;}
static void vTaskDelay(unsigned n){ticks+=n;}
static uintptr_t elf_find_sym_default(const char* name){
 if(missing&&!strcmp(name,missing))return 0;
 static const char* exports[]={EXPORTED_NAMES};
 for(const char* s:exports)if(!strcmp(name,s))return 1;return 0;
}
'''.replace('EXPORTED_NAMES', ','.join(json.dumps(n) for n in sorted(exported)))
    header = prelude + extract(text, 'bool allowedImport(') + '\n' + roles + '''
static bool file(void* context,const char* path,bool provider){
 std::ifstream input(path,std::ios::binary);if(!input)return false;
 std::vector<uint8_t> bytes(std::istreambuf_iterator<char>(input),{});
 if(!admitElf(bytes.data(),bytes.size(),provider?ElfRole::Driver:ElfRole::Application))return false;
 ++*static_cast<unsigned*>(context);return true;
}
}
'''
    output.mkdir(parents=True)
    (output / 'cohort_elf_admission.h').write_text(header)
    includes = [runtime / n for n in ('src', 'sdk/app', 'sdk/driver', 'sdk/hardware',
                 'lib/ArduinoJson/src', 'test/drivers/stubs', 'lib/elf_loader/include', 'test/native_bank_stubs')]
    includes += [output, tools / 'tests']
    inc = ['-I' + str(p) for p in includes]
    sanitize = ['-fsanitize='+sanitizers, '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer'] if sanitized else []
    if sanitized and sys.platform != 'darwin':
        sanitize.append('-no-pie')
    obj = output / 'validate.o'
    subprocess.run(['cc', '-std=c11', *sanitize, *inc, '-c',
                    str(runtime / 'lib/elf_loader/src/esp_elf_validate.c'), '-o', str(obj)], check=True)
    common = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-missing-field-initializers',
              '-Wno-misleading-indentation', '-DRISC_APP_REQUIREMENT_ROWS=24', '-DRISC_APP_POLICY_ROWS=24',
              *sanitize, *inc]
    if installed_catalog:
        common += ['-DRISC_INSTALLED_APP_CAPACITY=64']
    if shared_files:
        common += ['-DRISC_PROVIDER_CAPACITY=32']
    if sys.platform == 'darwin':
        # Clang diagnoses inactive host-only fields in unchanged production sources.
        common += ['-Wno-unused-private-field', '-Wno-unused-but-set-variable']
    # Check exact driver/application roles, unsafe-operation refusal and every missing import.
    standalone = '''#include "cohort_elf_admission.h"
int main(int argc,char**argv){
 assert(argc==3||argc==4);bool provider=!strcmp(argv[1],"driver");unsigned count=0;
 assert(CohortElf::file(&count,argv[2],provider)&&count==1);
 CohortElf::safe=false;assert(!CohortElf::file(&count,argv[2],provider));CohortElf::safe=true;
 assert(!CohortElf::file(&count,argv[2],!provider));
 if(argc==4){CohortElf::missing=argv[3];assert(!CohortElf::file(&count,argv[2],provider));}
 return 0;
}
'''
    (output / 'strict.cpp').write_text(standalone)
    subprocess.run([*common, str(output / 'strict.cpp'), str(obj), '-o', str(output / 'strict')], check=True)
    fixture_path = tools / 'tests/runtime_store_admission.cpp'
    fixture = fixture_path.read_text().replace('candidate.error(),hardwareCalls',
                   '(prepared?candidate.error():runtime.error()),hardwareCalls')
    needle = '  RiscBoot::Runtime runtime(runtimePort);'
    require(fixture.count(needle) == 1, 'Unexpected admission fixture')
    fixture = fixture.replace(needle,
        '  runtimePort.memoryHeap=[](risc_memory_heap_snapshot_v1*) -> int32_t {++hardwareCalls;return -1;};\n'
        '  runtimePort.randomBytes=[](void*,uint32_t) -> int32_t {++hardwareCalls;return -1;};\n' + needle)
    fixture = fixture.replace('#include <cstdio>', '#include <cstdio>\n#include "RiscDiagnosticSourceV1.h"')
    fixture = fixture.replace('bool bind(RiscBoot::Runtime& runtime) {',
        'risc_diagnostic_source_api_v1 diagnosticApi{1,sizeof(diagnosticApi),nullptr,\n'
        ' [](void*,uint32_t,char*,uint32_t,uint32_t*,uint64_t*,uint32_t*) -> int32_t {++hardwareCalls;return -1;}\n'
        '};\nbool bind(RiscBoot::Runtime& runtime) {\n'
        ' if(!runtime.registerPlatform(RISC_DIAGNOSTIC_SOURCE_CAPABILITY,1,RiscBoot::Runtime::Scope::Global,0,&diagnosticApi))return false;')
    fixture = fixture.replace('  RiscCpu::Hardware h{};',
        '  RiscCpu::Hardware h{};\n'
        '  h.usbPhyIdle=[](){++hardwareCalls;return false;};\n'
        '  h.usbPhySuspend=[](){++hardwareCalls;return false;};\n'
        '  h.usbPhyResume=[](){++hardwareCalls;return false;};')
    if installed_catalog:
        fixture = fixture.replace('  RiscCpu::Hardware h{};',
            '  RiscCpu::Hardware h{};\n'
            '  static RiscStorage::Worker worker;\n'
            '  static RiscCpu::StorageWorkBackend backend{&worker,[](){return true;},[](){++hardwareCalls;return false;},[](uint32_t){++hardwareCalls;}};\n'
            '  h.storageWork=&backend;')
    if shared_files:
        fixture = fixture.replace('  RiscCpu::Hardware h{};',
            '  RiscCpu::Hardware h{};\n'
            '  static RiscBoot::EntropyBackend entropy{nullptr,[](void*,uint64_t,void*,uint32_t)->int32_t{++hardwareCalls;return -1;},[](void*,uint64_t){return true;},[](void*){return true;}};\n'
            '  h.entropy=&entropy;\n'
            '  static RiscBoot::TcpListenerBackend tcp{nullptr,\n'
            '    [](void*,uint64_t,const risc_tcp_listen_v1*,uint64_t*)->int32_t{++hardwareCalls;return -1;},\n'
            '    [](void*,uint64_t,uint64_t,uint64_t*)->int32_t{++hardwareCalls;return -1;},\n'
            '    [](void*,uint64_t,uint64_t,void*,uint32_t,uint32_t*)->int32_t{++hardwareCalls;return -1;},\n'
            '    [](void*,uint64_t,uint64_t,const void*,uint32_t,uint32_t*)->int32_t{++hardwareCalls;return -1;},\n'
            '    [](void*,uint64_t,uint64_t)->int32_t{++hardwareCalls;return -1;},\n'
            '    [](void*,uint64_t){return true;},[](void*){return true;}};\n'
            '  h.tcpListener=&tcp;')
    # These inert callback slots match the qualified .75 source composition.
    # They must never be executed during admission; counters check that explicitly.
    (output / 'runtime_store_admission.cpp').write_text(fixture)
    definitions = ['STORE_ADMISSION_APP_DATA', 'RISC_PAIRED_APP_DATA=1', 'STORE_ADMISSION_COHORT',
                   'STORE_ADMISSION_KV_V2', 'STORE_ADMISSION_RUNTIME_FEATURES', 'STORE_ADMISSION_RADIO_IQ',
                   'STORE_ADMISSION_IQ_LIFECYCLE', 'STORE_ADMISSION_RADIO', 'STORE_ADMISSION_HCI',
                   'STORE_ADMISSION_I2S_RX', 'STORE_ADMISSION_UPDATE_PLATFORMS']
    if 'bool (*coldBoot)()' in (runtime / 'src/bootstrap/Runtime.h').read_text():
        definitions.append('STORE_ADMISSION_COLD_BOOT')
    sources = [runtime / n for n in ('src/bootstrap/Json.cpp', 'src/bootstrap/Board.cpp',
               'src/bootstrap/Runtime.cpp', 'src/runtime/drivers/ProviderGraphV2.cpp',
               'src/runtime/drivers/ProviderModuleV2.cpp', 'src/ports/esp32s3/CpuPort.cpp',
               'src/runtime/streams/AppStreamSessions.cpp', 'src/runtime/streams/ProviderQueueHost.cpp')]
    subprocess.run([*common, *([] if sys.platform == 'darwin' else ['-rdynamic']), *['-D' + d for d in definitions], *map(str, sources),
                    str(output / 'runtime_store_admission.cpp'), str(obj), '-ldl',
                    '-o', str(output / 'cohort')], check=True, timeout=180)
    return {'original_fixture_sha256': sha(fixture_path.read_bytes()),
            'selected_fixture_sha256': sha(fixture.encode()), 'header_sha256': sha(header.encode()),
            'native_admission_source_sha256': ADMISSION_SHA, 'sanitized': sanitized,
            'sanitizers': sanitizers if sanitized else None}


def build(a):
    version = getattr(a, 'version', '0.1.76')
    require(version in BUILD_SELECTIONS, 'Unknown Reader firmware selection')
    selected = BUILD_SELECTIONS[version]
    base_sha = selected['baseline_sha256']
    scene_sha, reader_sha = selected['scene_sha256'], selected['reader_sha256']
    image_name = f'X4-{version}-Reader-Panel-0.1.12-full-0x0.bin'
    require(not a.output.exists(), 'Use a new output directory')
    require(re.fullmatch('[0-9a-f]{40}', a.source_revision), 'Invalid source revision')
    runtime_tree = subprocess.check_output(['git', '-C', str(a.runtime), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    require(runtime_tree == RUNTIME_TREE, 'Wrong Runtime .75 source tree')
    require(not subprocess.check_output(['git', '-C', str(a.runtime), 'status', '--porcelain', '--untracked-files=no'], text=True),
            'Modified Runtime admission source')
    sys.path[:0] = [str(a.tools / 'scripts'), str(a.runtime / 'scripts')]
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from paired_bank_images import initial_bank_state, parse_record
    from native_binary_exports import segments
    raw = a.baseline.read_bytes()
    require(len(raw) == 0x1000000 and sha(raw) == base_sha, 'Not the exact qualified X4 ' + selected['baseline_version'] + ' image')
    pair = parse_record(raw[0xff2000:0xff2060], True)
    require(pair[2] == 0, 'Expected active bank zero')
    firmware = raw[0x10000:0x10000 + pair[3]]
    require(sha(firmware) == NATIVE_SHA and pair[6] == hashlib.sha256(firmware).digest(), 'Native firmware mismatch')
    require(raw[0x10000 + len(firmware):0x270000] == b'\xff' * (0x260000-len(firmware)), 'Native padding differs')
    require(b'RISC_APP_POLICY_ROWS:24\0' in firmware and b'RISC_APP_REQUIREMENT_ROWS:24\0' in firmware,
            'Native policy/requirement bounds mismatch')
    fs = raw[0x2f0000:0x800000]
    require(pair[7] == hashlib.sha256(fs).digest(), 'Baseline paired store hash mismatch')
    old = read_image(fs, 0x510000)
    require(len(old) == 92 and pack(old)[0] == fs, 'Baseline store is not reproduced byte-for-byte')
    require(sha(old['panel/driver.elf']) == PANEL_SHA, 'Wrong stable panel')
    exported, witness = native_witness(a.runtime, firmware)
    new = dict(old)
    for name in ('driver.elf', 'manifest.json'):
        new['ui-scene/' + name] = (a.scene / name).read_bytes()
    new['ebook_reader.json'] = (a.reader / 'ebook_reader.json').read_bytes()
    app = (a.reader / 'ebook_reader.elf').read_bytes()
    require(sha(new['ui-scene/driver.elf']) == scene_sha and sha(app) == reader_sha, 'Wrong qualified component bytes')
    for name, component_version in [('ui-scene/manifest.json', selected['scene_version']), ('ebook_reader.json', selected['reader_version'])]:
        before, after = json.loads(old[name]), json.loads(new[name])
        require(after['version'] == component_version, 'Incorrect component version')
        before.pop('version'); after.pop('version')
        require(before == after, 'Existing manifest policy changed')
    cohort = json.loads(old['cohort.json'])
    require(cohort['version'] == selected['baseline_version'] and cohort['firmware_sha256'] == NATIVE_SHA, 'Wrong cohort identity')
    cohort.update(version=version, source_revision=a.source_revision)
    new['cohort.json'] = encoded(cohort)
    require(new.keys() == old.keys() and {n for n in new if new[n] != old[n]} == ALLOWED, 'Unrelated internal files changed')
    a.output.mkdir(parents=True)
    write_store(a.output / 'baseline-store', old); write_store(a.output / 'store', new)
    (a.output / 'ebook_reader.elf').write_bytes(app)
    (a.output / 'native-exports.json').write_bytes(encoded(witness))
    modules = [(n, data, n.endswith('/driver.elf')) for n, data in sorted(new.items()) if n.endswith('.elf')]
    require(len(modules) == 37, 'Incomplete internal ELF set')
    modules.append(('ebook_reader.elf', app, False))
    for name, data, _ in modules:
        require(set(imports(data)) <= set(exported), 'Unresolved native import: ' + name)
    results = []
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    for sanitized in (False, True):
        directory = a.output / ('sanitized' if sanitized else 'plain')
        info = compile_admission(a.runtime, a.tools, directory, exported, sanitized)
        negative_count = 0
        for name, data, provider in modules:
            path = a.output / name if name == 'ebook_reader.elf' else a.output / 'store' / name
            command = [str(directory / 'strict'), 'driver' if provider else 'app', str(path)]
            subprocess.run(command, check=True, env=env, timeout=30)
            if name in ('ui-scene/driver.elf', 'ebook_reader.elf'):
                for symbol in imports(data):
                    subprocess.run(command + [symbol], check=True, env=env, timeout=30); negative_count += 1
        outcomes = []
        for previous in ('baseline-store', 'store'):
            result = subprocess.run([str(directory / 'cohort'), str(a.output / previous), str(a.output / 'store')],
                                    check=True, text=True, capture_output=True, env=env, timeout=45)
            (directory / (previous + '.log')).write_text(result.stdout + result.stderr)
            outcome = json.loads(result.stdout)
            require(outcome['prepared'] and outcome['cohort_validated'] and outcome['elf_count'] == 37
                    and outcome['hardware_calls'] == outcome['storage_calls'] == 0, 'Cohort validation failed: ' + str(outcome))
            outcomes.append(dict(outcome, active=previous))
        info.update(strict_modules=38, missing_import_rejections=negative_count,
                    wrong_role_rejections=38, unsafe_operation_rejections=38, cohorts=outcomes)
        results.append(info)
        print(('ASan/UBSan' if sanitized else 'Normal') + ': 38 ELF admissions, 41 missing-import rejections and both 37-module cohorts PASS', flush=True)
    require({p.relative_to(a.output / 'store').as_posix(): p.read_bytes() for p in (a.output / 'store').rglob('*') if p.is_file()} == new,
            'Admission changed store files')
    updated_fs, capacity = pack(new)
    require(pack(new)[0] == updated_fs, 'Nondeterministic output store')
    for label, data, expected in [('baseline', fs, old), ('output', updated_fs, new)]:
        path = a.output / (label + '-bootfs.bin'); path.write_bytes(data)
        dest = a.output / (label + '-independent'); dest.mkdir()
        subprocess.run([str(a.mkspiffs), '-u', str(dest), '-p', '256', '-b', '4096', '-s', str(0x510000), str(path)],
                       check=True, stdout=subprocess.DEVNULL, timeout=60)
        require({p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob('*') if p.is_file()} == expected,
                'Independent filesystem readback differs')
    bank = initial_bank_state(firmware, updated_fs, True)
    require(initial_bank_state(firmware, fs, True) == raw[0xff2000:0xff4000], 'Unexpected original paired-bank metadata')
    checked_pair = parse_record(bank[:96], True)
    require(checked_pair[6] == pair[6] and checked_pair[7] == hashlib.sha256(updated_fs).digest(), 'Output paired hashes incorrect')
    image = bytearray(raw); image[0x2f0000:0x800000] = updated_fs; image[0xff2000:0xff4000] = bank
    ranges = [(0, 0x2f0000), (0x800000, 0xff2000), (0xff4000, len(raw))]
    require(all(image[lo:hi] == raw[lo:hi] for lo, hi in ranges), 'Unexpected change outside store/paired record')
    require(read_image(bytes(image[0x2f0000:0x800000]), 0x510000) == new, 'Final BIN readback mismatch')
    segments(firmware)
    (a.output / image_name).write_bytes(image)
    report = {'schema': 'x4.reader-bin-overlay.v1', 'version': version,
        'image': {'name': image_name, 'bytes': len(image), 'flash_offset': 0, 'sha256': sha(image)},
        'baseline_sha256': base_sha, 'baseline_version': selected['baseline_version'], 'native_firmware_sha256': NATIVE_SHA, 'native_unchanged': True,
        'source_revision': a.source_revision, 'assembler_sha256': sha(Path(__file__).read_bytes()),
        'runtime_source_tree': runtime_tree, 'native_bank_source_sha256': ADMISSION_SHA,
        'native_validation_method': 'Exact ESP BIN checksum/SHA and complete source-ordered resolver tables; production source host admission',
        'native_original_elf_used': False, 'target_instructions_executed': False,
        'baseline_store_byte_reproduction': True, 'changed_internal_files': sorted(ALLOWED),
        'unchanged_internal_files': len(new) - len(ALLOWED), 'all_file_inventories': {'before': inventory(old), 'after': inventory(new)},
        'unchanged_ranges': [{'offset': lo, 'bytes': hi-lo, 'sha256': sha(raw[lo:hi])} for lo, hi in ranges],
        'panel_version': '0.1.12', 'panel_sha256': PANEL_SHA, 'panel_unchanged': True,
        'scene': {'version': selected['scene_version'], 'bytes': len(new['ui-scene/driver.elf']), 'sha256': scene_sha},
        'reader': {'version': selected['reader_version'], 'bytes': len(app), 'sha256': reader_sha, 'sd_path': 'Apps/ebook-reader/ebook_reader.elf'},
        'store_generator': capacity, 'independent_mkspiffs_sha256': sha(a.mkspiffs.read_bytes()),
        'independent_baseline_and_output_readbacks': True, 'paired_sha_crc_verified': True,
        'validation': results, 'hardware_tested': False, 'full_flash_overwrites_internal_data': True}
    (a.output / 'build-custody.json').write_bytes(encoded(report))
    print(json.dumps(report['image']), flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('baseline', 'runtime', 'tools', 'scene', 'reader', 'mkspiffs', 'output'):
        p.add_argument('--' + field, type=lambda s: Path(s).resolve(), required=True)
    p.add_argument('--source-revision', required=True)
    p.add_argument('--version', choices=tuple(BUILD_SELECTIONS), default='0.1.76')
    build(p.parse_args())
