#!/usr/bin/env python3
"""Configure only the product contract, then check its released selections."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ['RISCRTE_RUNTIME_ROOT']).resolve()
BASELINE = '3ac013bd21815bf18e42466b656dbc333665bf6b'
release = json.loads((ROOT / 'docs/native-idf61/released-profile.json').read_text())
pins = json.loads((ROOT / 'docs/native-idf61/preserved-inputs.json').read_text())
with tempfile.TemporaryDirectory() as name:
    work = Path(name)
    (work / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.22)
project(x4_contract NONE)
include("${RUNTIME_ROOT}/idf/product-profile.cmake")
file(WRITE "${CMAKE_BINARY_DIR}/profile.txt" "target=${RISC_NATIVE_TARGET}\\npartitions=${RISC_NATIVE_PARTITIONS}\\ndefinitions=${RISC_NATIVE_DEFINITIONS}\\nlinks=${RISC_NATIVE_LINK_OPTIONS}\\ncompile=${RISC_NATIVE_COMPILE_OPTIONS}\\nsources=${RISC_NATIVE_EXTRA_SOURCES}\\nincludes=${RISC_NATIVE_INCLUDE_DIRECTORIES}\\nsettings=${RISC_NATIVE_SETTINGS_HEADER}\\n")
''')
    build = work / 'build'
    subprocess.run(['cmake', '-S', str(work), '-B', str(build),
                    '-DRUNTIME_ROOT=' + str(RUNTIME),
                    '-DRISC_PRODUCT_PROFILE=' + str(ROOT / 'profiles/native-idf61.cmake')], check=True)
    profile = dict(line.split('=', 1) for line in (build / 'profile.txt').read_text().splitlines())
    assert profile['target'] == 'esp32s3-16mb-appdata-iq'
    expected = {flag[2:] for flag in release['flags'] if flag.startswith('-DRISC_') and not flag.startswith('-DRISC_TARGET=')}
    expected |= {key + '=' + str(value) for key, value in release['composition_definitions'].items()}
    assert set(profile['definitions'].split(';')) == expected
    assert not any(flag.startswith(('ARDUINO', 'CONFIG_')) for flag in expected)
    links = set(profile['links'].split(';'))
    assert set(release['composition_link_flags']) <= links
    assert {flag for flag in release['flags'] if flag.startswith('-Wl,-u,')} <= links
    assert '-Wl,-u,risc_x4_native_ready' in links
    assert {'-Wl,-u,risc_tcp_listener_abi', '-Wl,-u,risc_entropy_abi'} <= links
    assert not any('risc_file_source_abi' in link for link in links)
    assert not any(flag.startswith('RISC_NATIVE_FILE_SOURCE=') for flag in expected)
    assert '-fstack-usage' in profile['compile'].split(';')
    assert profile['sources'] == str(ROOT / 'minimal/native/X4EarlyBoot.cpp')
    partitions = Path(profile['partitions']).read_bytes()
    # Exact released standard-store CSV (including the deliberately empty gap).
    assert hashlib.sha256(partitions).hexdigest() == pins['partitions_sha256']
    entries = [line.split(',') for line in partitions.decode().splitlines() if line and not line.startswith('#')]
    selected = {row[0]: (int(row[3], 0), int(row[4], 0)) for row in entries}
    assert selected == {'nvs': (0x9000, 0x6000), 'app0': (0x10000, 0x260000),
        'appdata': (0x270000, 0x80000), 'bootfs0': (0x2f0000, 0x510000),
        'app1': (0x800000, 0x260000), 'bootfs1': (0xae0000, 0x510000),
        'otadata': (0xff0000, 0x2000), 'bank_state': (0xff2000, 0x2000)}
    selection = (build / 'x4-native-idf61/selection.txt').read_text()
    payload, composition = selection.rsplit('composition_sha256=', 1)
    assert hashlib.sha256(payload.encode()).hexdigest() == composition.strip()
    assert composition.strip() != release['compiled_composition_sha256']
    header = (build / 'x4-native-idf61/X4NativeBuildIdentity.h').read_text()
    assert composition.strip() in header and BASELINE in header
    assert release['source_runtime_revision'] in header
    settings = work / 'settings.cpp'
    settings.write_text('''#include <cstdint>
#include <cstring>
#include <cassert>
#include "''' + profile['settings'] + '''"
constexpr uint8_t owner[]=RISC_NATIVE_SETTINGS_LOGICAL_OWNER;
struct Writer {const char* id; unsigned ns;};
constexpr Writer writers[]={RISC_NATIVE_SETTINGS_WRITERS};
static_assert(sizeof(owner)==16 && owner[15]==1);
static_assert(RISC_NATIVE_SETTINGS_VOLUME_INSTANCE==9);
static_assert(sizeof(writers)/sizeof(writers[0])==6);
static_assert(RISC_NATIVE_SETTINGS_MAX_WRITERS==6 && RISC_NATIVE_SETTINGS_NAMESPACE_MASK==3);
int main(){
 const char* expected[]={"settings","paper_clock","battery","ble_scanner","contexts","wifi_settings"};
 assert(!std::memcmp(owner,"X4-RTE-SETTINGS",15));
 for(unsigned i=0;i<6;++i){assert(!std::strcmp(writers[i].id,expected[i]));assert(writers[i].ns==(i==5?6u:1u));}
}
''')
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    str(settings), '-o', str(work / 'settings')], check=True)
    subprocess.run([str(work / 'settings')], check=True)
    # SDK migration must not replace the rail primitive or admitted board/panel providers.
    for path, digest in pins['product_files'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
print('X4 native profile: exact released features/partitions/settings; unchanged rail/board/panel; new candidate identity PASS')
