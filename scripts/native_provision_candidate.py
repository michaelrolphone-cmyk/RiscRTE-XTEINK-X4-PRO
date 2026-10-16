#!/usr/bin/env python3
"""Freeze and qualify an unreleased SDK6.1 product candidate without device I/O.

The historical release recipes are deliberately not called. This additive .123 recipe replaces only reviewed Home/catalog payloads and boot
grants; unrelated store, SD content, partition and settings identities survive.
"""
import argparse
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import zipfile
import native_idf61_build as controlled_build
from native_idf61_provenance import effective_sdkconfig, compiler_definitions, local_module, expand_response_files, compiler_family, compiler_command

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/native-provision-123/released-baseline.json'
SDK_REVISION = 'fff9895c82d744c7237be8847347bdd1b07c6643'
REQUIRED_ROLES = {'product', 'runtime', 'system', 'drivers', 'sdk', 'image_helper', 'reader', 'utilities'}
BOUNDARY_SYMBOLS = ('risc_tcp_listener_abi', 'risc_entropy_abi', 'risc_sdmmc_host_abi')
ARTIFACT_KEYS = {'firmware_bin', 'firmware_elf', 'firmware_map', 'bootloader', 'partitions',
                 'sdkconfig', 'compile_commands', 'project_description', 'flasher_args',
                 'bootloader_elf', 'bootloader_compile_commands', 'bootloader_sdkconfig', 'x4_selection',
                 'sdkconfig_json', 'sdkconfig_header', 'bootloader_sdkconfig_header',
                 *{'response_' + name for name in ('cflags', 'cxxflags', 'asmflags', 'ldflags')},
                 *{'boot_response_' + name for name in ('cflags', 'cxxflags', 'asmflags', 'ldflags')}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def run(*args, **kwargs):
    return subprocess.check_output([str(x) for x in args], **kwargs)


def git(root, *args):
    return run('git', '-C', root, *args, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})


def clean_source(root, revision):
    root = Path(root).resolve()
    require(re.fullmatch(r'[0-9a-f]{40}', revision), 'Full immutable source revision required')
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == revision, 'Source HEAD differs: ' + str(root))
    require(not git(root, 'status', '--porcelain', '--untracked-files=no').strip(), 'Dirty source: ' + str(root))
    require(not git(root, 'ls-files', '--others', '--exclude-standard').strip(), 'Untracked source inputs: ' + str(root))
    submodules = git(root, 'submodule', 'status', '--recursive').decode().splitlines()
    require(all(line.startswith(' ') for line in submodules), 'Uninitialized/changed source submodule: ' + str(root))
    return {'revision': revision, 'tree': git(root, 'rev-parse', 'HEAD^{tree}').decode().strip(),
            'submodules': [line.strip() for line in submodules]}


def safe_path(root, relative):
    path = PurePosixPath(relative)
    require(not path.is_absolute() and str(path) == relative and '..' not in path.parts,
            'Non-canonical artifact path')
    result = (root / relative).resolve()
    require(result.is_relative_to(root.resolve()) and result.is_file(), 'Artifact outside build or missing: ' + relative)
    return result


def parse_sources(rows):
    result = {}
    for row in rows:
        name, value = row.split('=', 1)
        require(name not in result and re.fullmatch('[a-z_]+', name), 'Duplicate/invalid source role')
        result[name] = Path(value).resolve()
    require(REQUIRED_ROLES <= result.keys(), 'Missing source roots: ' + str(REQUIRED_ROLES - result.keys()))
    require(result['product'] == ROOT, 'Product source must be this recipe checkout')
    return result


def imports(data):
    from elftools.elf.elffile import ELFFile
    elf = ELFFile(io.BytesIO(data))
    require(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_XTENSA', 'Not ELF32 LE Xtensa')
    return {s.name for section in elf.iter_sections() if section['sh_type'] in ('SHT_DYNSYM', 'SHT_SYMTAB')
            for s in section.iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF'}


def reject_private(store, runtime):
    inventory = set()
    for version in (1, 2):
        text = (runtime / ('lib/elf_loader/include/private/privileged_os_cpu_symbols_v%d.def' % version)).read_text()
        inventory.update(re.findall(r'RISC_OS_CPU_SYMBOL\((\w+)\)', text))
    results = {}
    for name, data in sorted(store.items()):
        if name.endswith('.elf'):
            symbols = imports(data)
            require(not symbols & inventory, 'Private OS/CPU provider cannot be reused or authorized by a sidecar: ' + name + ': ' + str(sorted(symbols & inventory)))
            results[name] = sorted(symbols)
    return results


def setup_modules(sources):
    sys.path[:0] = [str(sources['runtime'] / 'scripts'), str(sources['image_helper'] / 'scripts')]
    return importlib.import_module('prepare_preserving_update'), importlib.import_module('read_only_spiffs')


def capabilities(value):
    if isinstance(value, dict):
        if 'capability' in value:
            yield value['capability']
        for item in value.values():
            yield from capabilities(item)
    elif isinstance(value, list):
        for item in value:
            yield from capabilities(item)


def reject_unselected_file_source(files):
    # file.open is the released SD-volume workflow. file.open.source is a
    # separate opt-in scratch backend and is not selected for this product.
    for name, raw in files.items():
        if name.endswith('.json'):
            require('file.open.source' not in capabilities(json.loads(raw)),
                    'Unselected file-source capability in released X4 payload: ' + name)


def verify_selected_backend_markers(elf_bytes):
    import check_runtime_store_admission as admission
    for name in BOUNDARY_SYMBOLS:
        require(admission.native_symbol_bytes(elf_bytes, name) == b'\x01\0\0\0',
                'Native public backend missing: ' + name)


def x4_backend_selection(symbols, labels):
    require('risc_file_source_abi' not in symbols and
            not any(label.startswith('RiscFileSource::') for label in labels),
            'Unselected X4 native file-source backend linked')
    return dict(file_source_enabled=False)


def baseline_bytes(path, contract, sources):
    update, spiffs = setup_modules(sources)
    image = path.read_bytes()
    require(len(image) == contract['factory_bytes'] and sha(image) == contract['factory_sha256'], 'Exact released factory required')
    geometry = update.layout(image)
    require(not geometry[0] and geometry[3] == 0x510000, 'X4 standard paired ABI2 layout required')
    _, native, packed = update.pair(image, 0, geometry)
    require(sha(native) == contract['native_sha256'], 'Released native binding differs')
    store = spiffs.read_image(packed, geometry[3])
    actual = {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in sorted(store.items())}
    require(actual == contract['files'], 'Released payload inventory differs')
    require(json.loads(store['cohort.json'])['source_revision'] == contract['source_revision'], 'Released source differs')
    reject_private(store, sources['runtime'])
    reject_unselected_file_source(store)
    return image, native, store


def released_sd(path, contract, runtime):
    """Exact released full-card package; never synthesize settings/user files."""
    require(path is not None, 'Complete released SD archive required')
    return released_sd_bytes(path.read_bytes(), contract, runtime)


def released_sd_bytes(raw, contract, runtime):
    """Validate and consume one immutable archive byte snapshot."""
    sd = contract['sd']
    require(len(raw) == sd['bytes'] and sha(raw) == sd['sha256'], 'Exact released complete SD archive required')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) == sd['file_count'] and set(names) == set(sd['files']), 'SD package inventory differs')
        files = {}
        for name in names:
            relative = PurePosixPath(name)
            require(not relative.is_absolute() and str(relative) == name and '..' not in relative.parts, 'Unsafe SD member')
            data = archive.read(name)
            row = sd['files'][name]
            require(len(data) == row['bytes'] and sha(data) == row['sha256'], 'Released SD payload differs: ' + name)
            files[name] = data
    reject_private(files, runtime)
    reject_unselected_file_source(files)
    require(sum(name.endswith('.elf') for name in files) == sd['elf_count'], 'Incomplete SD ELF inventory')
    require(any(name.startswith('Drivers/usb-device-msc-esp32s3/') and name.endswith('.elf') for name in files), 'Device-MSC SD provider missing')
    return files


def verify_x4_startup(blobs, build, compiler, lock, sources):
    """Run the existing final-linked GPIO1/readiness proof on these exact bytes."""
    text = blobs['x4_selection'].decode()
    payload, digest = text.rsplit('composition_sha256=', 1)
    require(sha(payload.encode()) == digest.strip(), 'Invalid X4 selection digest')
    selection = dict(line.split('=', 1) for line in text.splitlines())
    require(selection['product_source'] == lock['sources']['product']['revision'] and
            selection['runtime_source'] == lock['sources']['runtime']['revision'], 'X4 target source identity differs from lock')
    require(selection['sdk_source'] == SDK_REVISION, 'X4 SDK selection differs')
    for name, digest in selection.items():
        if name.startswith('sha256:'):
            path = safe_path(ROOT, name[len('sha256:'):])
            require(sha(path.read_bytes()) == digest, 'X4 selection input differs: ' + str(path))
    for key in ('firmware_bin', 'firmware_elf'):
        require(b'X4_VERSION=0.1.123-provision-candidate' in blobs[key], 'Wrong X4 native successor version')
        require(b'RISC_RUNTIME_VERSION:0.4.7\0' in blobs[key], 'X4 successor requires Runtime 0.4.7')
    with tempfile.TemporaryDirectory(prefix='x4-native-startup-') as tmp:
        output = Path(tmp) / 'proof.json'
        run(sys.executable, ROOT / 'minimal/test/verify_native_idf61_target.py',
            '--elf', safe_path(build, lock['native_files']['firmware_elf']['path']),
            '--selection', safe_path(build, lock['native_files']['x4_selection']['path']),
            '--objdump', compiler.with_name('xtensa-esp-elf-objdump'), '--output', output)
        proof = json.loads(output.read_bytes())
    require(proof['elf_sha256'] == sha(blobs['firmware_elf']) and
            len(proof['bypass_mutations_rejected']) == 5 and not proof['hardware_qualified'], 'Incomplete X4 linked startup proof')
    return proof


def descriptor(data):
    require(len(data) >= 288 and struct.unpack_from('<I', data, 32)[0] == 0xabcd5432, 'Missing ESP app descriptor')
    value = lambda start, size: data[start:start + size].split(b'\0', 1)[0].decode('ascii')
    return dict(project_name=value(80, 32), version=value(48, 32), idf_version=value(144, 32), secure_version=struct.unpack_from('<I', data, 36)[0])


def artifact_paths(build):
    project = json.loads((build / 'project_description.json').read_bytes())
    flash = json.loads((build / 'flasher_args.json').read_bytes())
    require(Path(project['config_file']).resolve() == (build / 'sdkconfig').resolve(), 'Build must own the exact selected sdkconfig')
    app = Path(flash['app']['file'])
    require(not app.is_absolute(), 'Flash descriptor app must be relative')
    return dict(firmware_bin=app.as_posix(), firmware_elf=app.with_suffix('.elf').as_posix(),
                firmware_map=app.with_suffix('.map').as_posix(), bootloader=flash['bootloader']['file'],
                partitions=flash['partition-table']['file'], sdkconfig='sdkconfig',
                compile_commands='compile_commands.json', project_description='project_description.json',
                flasher_args='flasher_args.json', bootloader_elf='bootloader/bootloader.elf',
                bootloader_compile_commands='bootloader/compile_commands.json', bootloader_sdkconfig='bootloader/config/sdkconfig.json', x4_selection='x4-native-idf61/selection.txt',
                sdkconfig_json='config/sdkconfig.json', sdkconfig_header='config/sdkconfig.h',
                bootloader_sdkconfig_header='bootloader/config/sdkconfig.h',
                **{'response_' + name: 'toolchain/' + name for name in ('cflags', 'cxxflags', 'asmflags', 'ldflags')},
                **{'boot_response_' + name: 'bootloader/toolchain/' + name for name in ('cflags', 'cxxflags', 'asmflags', 'ldflags')})


def verify_sources(lock, sources):
    require(set(lock['sources']) == set(sources), 'Source role set differs from frozen lock')
    for role, root in sorted(sources.items()):
        require(clean_source(root, lock['sources'][role]['revision']) == lock['sources'][role], 'Source closure differs: ' + role)
    require(lock['sources']['sdk']['revision'] == SDK_REVISION, 'Unreviewed SDK revision')


def freeze(sources, build, compiler, output, candidate_version):
    require(not output.exists(), 'Lock output already exists')
    require(candidate_version == '0.1.123', 'X4 successor recipe requires explicit candidate version 0.1.123; no publication is implied')
    pins = {role: clean_source(root, git(root, 'rev-parse', 'HEAD').decode().strip()) for role, root in sorted(sources.items())}
    require(pins['sdk']['revision'] == SDK_REVISION, 'Unreviewed SDK revision')
    require('-idf61.' not in candidate_version or candidate_version.endswith(pins['runtime']['revision'][:12]), 'Candidate suffix must identify Runtime source')
    version = run(compiler, '--version').decode().splitlines()[0]
    require('15.2.0' in version and 'esp-15.2.0_20251204' in version, 'Exact native GCC15 release required')
    paths = artifact_paths(build)
    files = {key: {'path': path, 'bytes': safe_path(build, path).stat().st_size,
                   'sha256': sha(safe_path(build, path).read_bytes())} for key, path in paths.items()}
    lock = dict(schema=1, publication_enabled=False, candidate_version=candidate_version,
                baseline_contract_sha256=sha(CONTRACT.read_bytes()), sources=pins, native_files=files,
                compiler=dict(version=version, sha256=sha(compiler.read_bytes())),
                compiler_family=compiler_family(compiler),
                status='frozen-inputs-only-not-qualified')
    output.write_bytes(encoded(lock))
    return lock



def arduino_runtime_symbols(labels):
    # setup/loop are Runtime-owned routines called by native app_main. Their
    # familiar names do not imply an Arduino framework dependency.
    forbidden = re.compile(r'(^|[^A-Za-z0-9_])(?:initArduino|initVariant|loopTask|HardwareSerial|HWCDC::|String::)')
    return [name for name in labels if forbidden.search(name)]


def checked_artifacts(lock, build):
    require(set(lock['native_files']) == ARTIFACT_KEYS, 'Incomplete native artifact hash lock')
    result = {}
    for key, row in lock['native_files'].items():
        data = safe_path(build, row['path']).read_bytes()
        require(len(data) == row['bytes'] and sha(data) == row['sha256'], 'Native artifact differs from lock: ' + key)
        result[key] = data
    return result


def verify_native(lock, sources, build, compiler, contract, baseline):
    from elftools.elf.elffile import ELFFile
    from release_assets import esp_image
    from paired_candidate import partitions, APP_DATA_EXPECTED
    from radio_iq_proof import prove
    from verify_update_elf import verify_native_store_abi, public_exports
    import check_runtime_store_admission as admission
    blobs = checked_artifacts(lock, build)
    require(sha(compiler.read_bytes()) == lock['compiler']['sha256'], 'Compiler bytes differ')
    require(run(compiler, '--version').decode().splitlines()[0] == lock['compiler']['version'], 'Compiler version differs')
    for key in ('firmware_bin', 'bootloader'):
        esp_image(blobs[key])
        require(blobs[key][3] >> 4 == 4, '16MiB flash image flag required')
    require(0 < len(blobs['firmware_bin']) <= 0x260000 and 0 < len(blobs['bootloader']) <= 0x8000, 'Native image exceeds released slot')
    table = blobs['partitions']
    partitions(table, APP_DATA_EXPECTED)
    require(table == baseline[0x8000:0x8000 + len(table)], 'Partition bytes changed')
    desc = descriptor(blobs['firmware_bin'])
    require(desc['project_name'] == contract['app_descriptor']['project_name'], 'App descriptor project_name would break installed native firmware admission')
    require(desc['secure_version'] == contract['app_descriptor']['secure_version'], 'Unreviewed security version change')
    require(re.match(r'v?6\.1(?:\D|$)', desc['idf_version']), 'Native descriptor does not identify SDK6.1')
    effective_config = effective_sdkconfig(blobs)
    elf = ELFFile(io.BytesIO(blobs['firmware_elf']))
    require(elf['e_type'] == 'ET_EXEC' and elf['e_machine'] == 'EM_XTENSA', 'Not a native Xtensa executable')
    symbols = {s.name: s for s in elf.get_section_by_name('.symtab').iter_symbols()}
    forbidden = ('initArduino', 'loopTask', '_Z11initArduinov', 'risc_usb_controller_idf61_policy')
    require(not any(name in symbols for name in forbidden), 'Arduino entry or unselected USB controller linked')
    demangler = compiler.with_name('xtensa-esp-elf-c++filt')
    labels = run(demangler, input=('\n'.join(symbols) + '\n').encode()).decode().splitlines()
    require(not arduino_runtime_symbols(labels), 'Arduino runtime symbol linked')
    backend_selection = x4_backend_selection(symbols, labels)
    for wanted, prefix in {'RuntimeStreams::(anonymous namespace)::registry': '.dram',
                           'vPortEvaluateYieldFromISR': '.iram', 'risc_elf_clock_gettime32': '.flash.text'}.items():
        matches = [symbol for name, symbol in zip(labels, symbols.values()) if name == wanted]
        require(len(matches) == 1 and isinstance(matches[0]['st_shndx'], int), 'Missing native placement/time32 boundary ' + wanted)
        require(elf.get_section(matches[0]['st_shndx']).name.startswith(prefix), 'Native placement boundary differs: ' + wanted)
    display_hooks = [symbol for name, symbol in zip(labels, symbols.values()) if name == 'RiscCpu::selectedDisplayBackend()' and symbol['st_info']['bind'] == 'STB_GLOBAL']
    require(not display_hooks, 'X4 must retain its released panel provider, without a new native display hook')
    project = json.loads(blobs['project_description'])
    require(Path(project['config_file']).resolve() == safe_path(build, lock['native_files']['sdkconfig']['path']), 'Build config differs from locked sdkconfig')
    require(project['target'] == 'esp32s3' and Path(project['idf_path']).resolve() == sources['sdk'], 'Build SDK/target differs')
    require(not any('arduino' in name.lower() for name in project['build_components']), 'Arduino component selected')
    require(symbols.get('app_main') is not None and symbols['app_main']['st_shndx'] != 'SHN_UNDEF', 'Native app_main missing')
    for name in ('esp_ota_mark_app_valid_cancel_rollback', 'esp_ota_mark_app_invalid_rollback_and_reboot'):
        require(name in symbols and symbols[name]['st_shndx'] != 'SHN_UNDEF', 'Missing rollback operation ' + name)
    source_marker = ('RTE_SOURCE=' + lock['sources']['runtime']['revision']).encode() + b'\0'
    for key in ('firmware_bin', 'firmware_elf'):
        require(source_marker in blobs[key] and contract['target'].encode() + b'\0' in blobs[key], 'Native source/target identity differs')
        require(set(re.findall(rb'RTE_SOURCE=([^\x00\s]+)', blobs[key])) == {lock['sources']['runtime']['revision'].encode()}, 'Ambiguous Runtime identity')
    for name, prefix in (('risc_app_policy_rows', 'RISC_APP_POLICY_ROWS'), ('risc_app_requirement_rows', 'RISC_APP_REQUIREMENT_ROWS')):
        require(admission.native_symbol_bytes(blobs['firmware_elf'], name) == (prefix + (':32\0' if prefix == 'RISC_APP_POLICY_ROWS' else ':24\0')).encode(), 'Native policy bounds changed')
    verify_selected_backend_markers(blobs['firmware_elf'])
    require(('risc_native_settings_admission' in symbols) == (contract['product'] == 'x4'), 'Product settings backend selection changed')
    require(('risc_usb_phy_resource_enabled' in symbols) == (contract['product'] == 'x4'), 'USB PHY selection changed')
    require(admission.native_symbol_bytes(blobs['firmware_elf'], 'risc_installed_app_capacity') == (64).to_bytes(4, 'little'), 'Native installed-app capacity differs')
    family = compiler_family(compiler)
    require(lock.get('compiler_family') == family and family['gcc']['sha256'] == lock['compiler']['sha256'],
            'Compiler family differs from frozen lock')
    compile_rows = json.loads(blobs['compile_commands']) + json.loads(blobs['bootloader_compile_commands'])
    require(compile_rows, 'Empty native compilation database')
    source_files = {}
    roots = sorted(sources.items(), key=lambda item: len(str(item[1])), reverse=True)
    runtime_rows = []
    profile = (ROOT / 'profiles/native-provision-123.cmake').read_text()
    definitions = dict(flag.split('=', 1) for flag in re.findall(r'\b(?:RISC_[A-Z0-9_]+|BOARD_XTEINK_X4_PRO)=\d+\b', profile))
    definitions.update(RISC_NATIVE_SERIAL_SD_PROVIDER='\"x4pro-sd\"', RISC_NATIVE_ESP_IDF='1', RISC_TARGET='\"' + contract['target'] + '\"')
    for row in compile_rows:
        source = Path(row['file']).resolve()
        require('framework-arduino' not in str(source).lower() and source.name not in ('esp32-hal-misc.c', 'Arduino.cpp'), 'Arduino core compiled')
        if not source.is_relative_to(build.resolve()):
            owner = next(((name, root) for name, root in roots if source.is_relative_to(root)), None)
            require(owner is not None, 'Compilation input outside immutable source roots: ' + str(source))
            role, root = owner
            relative = source.relative_to(root).as_posix()
            repository = Path(git(source.parent, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
            revision = lock['sources'][role]['revision']
            if repository != root:
                require(repository.is_relative_to(root), 'Source submodule escapes its pinned repository')
                subpath = repository.relative_to(root).as_posix()
                known = {line.split()[1]: line.split()[0] for line in lock['sources'][role]['submodules']}
                require(subpath in known, 'Compilation source belongs to an unpinned nested repository')
                revision = known[subpath]
            expected = git(repository, 'show', revision + ':' + source.relative_to(repository).as_posix())
            require(source.read_bytes() == expected, 'Compilation input differs from immutable source: ' + relative)
            source_files[role + '/' + relative] = sha(expected)
        else:
            source_files['generated/' + source.relative_to(build.resolve()).as_posix()] = sha(source.read_bytes())
        command = row.get('command') or shlex.join(row['arguments'])
        arguments = expand_response_files(shlex.split(command), build, row['directory'], blobs, lock['native_files'])
        compiler_command(arguments, compiler, family)
        if source.is_relative_to(sources['runtime'] / 'src'):
            defined = compiler_definitions(arguments, definitions)
            require(defined.get('RISC_NATIVE_FILE_SOURCE', '0') == '0', 'Unselected X4 native file-source backend compiled')
            runtime_rows.append(command)
    overlays = [Path(row['file']).resolve() for row in compile_rows if Path(row['file']).name == 'X4EarlyBoot.cpp']
    require(len(overlays) == 1 and overlays[0] == (ROOT / 'minimal/native/X4EarlyBoot.cpp').resolve(), 'Exact committed X4 startup overlay must be compiled')
    require(runtime_rows, 'Resident Runtime compilation rows missing')
    require(not re.search(r'framework-arduino|libFrameworkArduino|/cores/esp32/', blobs['firmware_map'].decode(errors='replace')), 'Arduino linked into map')
    require('RISC_NATIVE_PROVIDER_POLICY_HEADER' not in ' '.join(runtime_rows), 'Unselected private USB controller policy present')
    with tempfile.TemporaryDirectory(prefix='native-idf61-elf-bin-') as tmp:
        for binary, executable in (('firmware_bin', 'firmware_elf'), ('bootloader', 'bootloader_elf')):
            out = Path(tmp) / (binary + '.bin')
            extra = ['--elf-sha256-offset', '0xb0', '--flash-mmu-page-size', '64KB'] if binary == 'firmware_bin' else []
            run(sys.executable, '-m', 'esptool', '--chip', 'esp32s3', 'elf2image', '--flash-mode', 'dio', '--flash-freq', '80m', '--flash-size', '16MB', '--min-rev-full', '0', '--max-rev-full', '99', *extra, '-o', out, safe_path(build, lock['native_files'][executable]['path']))
            require(out.read_bytes() == blobs[binary], 'ELF/BIN correspondence differs: ' + binary)
    startup = verify_x4_startup(blobs, build, compiler, lock, sources)
    spec = importlib.util.spec_from_file_location('x4_bootlog_memory', ROOT / 'minimal/test/verify_native_idf61_bootlog_memory.py')
    memory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(memory)
    bootlog = memory.proof(blobs['firmware_elf'])
    require(bootlog['input_kind'] == 'final-elf' and bootlog['copied_bytes_external'] == 4528,
            'Final native bootlog placement proof required')
    require(any(name.startswith('RiscProvisionRequest::bind(') for name in labels), 'Selected native provision-request backend missing')
    require(any(name.startswith('RiscPackageVolume::bind(') for name in labels), 'Selected native internal package-volume backend missing')
    serial = verify_serial(sources, build, compiler, lock, blobs)
    return blobs, dict(serial_files=serial, **backend_selection, linked_memory=linked_memory(elf, blobs['firmware_map']), x4_startup=startup, x4_bootlog_memory=bootlog, effective_config=effective_config, app_descriptor=desc, native_layout=verify_native_store_abi(blobs['firmware_elf'], 2),
                       radio_iq=prove(blobs['firmware_elf'], contract['target']),
                       public_export_count=len(public_exports(elf)), source_files=source_files,
                       arduino_core_linked=False, ordinary_app_payloads_rebuilt=True,
                       unselected_usb_host_controller=False, elf_bin_identical=True)


def verify_serial(sources, build, compiler, lock, blobs):
    """Final linked generic RTEF1 evidence; no client commands or device I/O."""
    from native_provision_serial import verify_receipts
    startup = verify_receipts(lock, sources)
    tool = sources['runtime'] / 'test/prove_native_serial_workspace.py'
    output = run(sys.executable, tool,
                 safe_path(build, lock['native_files']['firmware_elf']['path']),
                 '--workspace', 'endpoint', '--workspace', 'provider', '--external', '1',
                 '--objdump', compiler.with_name('xtensa-esp-elf-objdump')).decode()
    require('Serial endpoint:' in output and 'Serial provider:' in output,
            'Incomplete final linked serial placement proof')
    return dict(firmware_elf_sha256=sha(blobs['firmware_elf']),
                tool_sha256=sha(tool.read_bytes()), output=output,
                endpoint_selected=True, boot_store_read_only=True,
                private_appdata_directory='/appdata/.serial-files',
                **startup['selection'], production_startup_tests=startup,
                metadata_protocol='RTEF1', firmware_flashing_via_rtef1=False,
                hardware_tested=False)


def linked_memory(elf, raw_map):
    """Record final linked allocation and remaining bytes in each RAM region."""
    text = raw_map.decode()
    memory = text.split('Memory Configuration', 1)[1].split('Linker script and memory map', 1)[0]
    result = {}
    for name, origin, length in re.findall(r'^([\w.]+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)', memory, re.M):
        if not any(part in name for part in ('dram', 'iram', 'extern_ram')):
            continue
        start, size = int(origin, 16), int(length, 16)
        sections = [{'name': s.name, 'address': s['sh_addr'], 'bytes': s['sh_size']}
                    for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size'] and
                    start <= s['sh_addr'] < start + size]
        end = max([start, *[s['address'] + s['bytes'] for s in sections]])
        require(end <= start + size, 'Linked RAM section exceeds region ' + name)
        result[name] = {'origin': start, 'length': size, 'linked_end': end,
                        'tail_margin_bytes': start + size - end, 'sections': sections}
    require('dram0_0_seg' in result, 'Final native DRAM region missing')
    return result


def compose_store(before, firmware, lock, packages):
    from native_provision_payloads import compose
    return compose(before, firmware, lock, packages)


def make_images(baseline, firmware, bootloader, packed):
    from paired_bank_images import initial_bank_state
    from prepare_preserving_update import pair, layout
    candidate = bytearray(baseline)
    candidate[0x10000:0x270000] = firmware + b'\xff' * (0x260000 - len(firmware))
    candidate[0x2f0000:0x800000] = packed
    state = initial_bank_state(firmware, packed, True, False)
    candidate[0xff2000:0xff2000 + len(state)] = state
    require(pair(candidate, 0, layout(candidate))[1:] == (firmware, packed), 'Native/store bank binding failed')
    for start, end in ((0, 0x10000), (0x270000, 0x2f0000), (0x800000, 0xff2000), (0xff3000, 0x1000000)):
        require(candidate[start:end] == baseline[start:end], 'Protected released range changed')
    # Old-bootloader image is an offline transition fixture, never a delivered kit.
    transition = bytes(candidate)
    candidate[:0x8000] = bootloader + b'\xff' * (0x8000 - len(bootloader))
    return bytes(candidate), transition


def qualify(args, sources, *, build_proof=None, package_proof=None):
    require(Path(controlled_build.__file__).resolve() == ROOT / 'scripts/native_idf61_build.py',
            'Controlled producer must come from this product checkout')
    controlled_build.validate_build_proof(build_proof, sources, args.native_build, args.compiler)
    from native_provision_payloads import verify_packages, preservation_receipt, write_feed
    packages = verify_packages(package_proof, sources)
    contract = json.loads(CONTRACT.read_bytes())
    lock = json.loads(args.lock.read_bytes())
    require(lock.get('package_build') == package_proof.receipt, 'Package lock differs')
    require(lock.get('schema') == 1 and lock.get('publication_enabled') is False, 'Only unreleased candidate locks accepted')
    require(lock['baseline_contract_sha256'] == sha(CONTRACT.read_bytes()), 'Released baseline contract differs')
    require(lock['candidate_version'] == contract['successor_version'] == '0.1.123', 'Frozen X4 successor version differs')
    build_closure = controlled_build.validate_build_proof(build_proof, sources, args.native_build, args.compiler, lock)
    verify_sources(lock, sources)
    require(not args.output.exists(), 'Qualification output must be new')
    baseline, old_native, before = baseline_bytes(args.baseline, contract, sources)
    blobs, native_proof = verify_native(lock, sources, args.native_build, args.compiler, contract, baseline)
    sd_archive = args.sd_archive.read_bytes()
    sd_files = released_sd_bytes(sd_archive, contract, sources['runtime'])
    after = compose_store(before, blobs['firmware_bin'], lock, packages)
    payload_preservation = preservation_receipt(before, after)
    reject_private(after, sources['runtime'])
    from current_bootfs import build
    packed, packing = build(after, size=0x510000)
    require(build(after, size=0x510000)[0] == packed, 'Non-deterministic bootfs packing')
    factory, transition = make_images(baseline, blobs['firmware_bin'], blobs['bootloader'], packed)
    qualification = local_module(ROOT, 'native_provision_qualification.py', 'x4_provision_qualification')
    sd_admission = qualification.admit_sd(sources, blobs['firmware_elf'], sd_files, contract, sanitized=False)
    sd_admission_sanitized = qualification.admit_sd(sources, blobs['firmware_elf'], sd_files, contract, sanitized=True)
    admission = qualification.admit_product(sources, blobs['firmware_elf'], before, after, native_proof, sanitized=False)
    admission_sanitized = qualification.admit_product(sources, blobs['firmware_elf'], before, after, native_proof, sanitized=True)
    require(admission['elf_count'] == admission_sanitized['elf_count'] == contract['elf_count'], 'Incomplete product ELF admission')
    preservation = qualification.preservation_model(baseline, transition, contract['factory_sha256'])
    checked_artifacts(lock, args.native_build)
    controlled_build.validate_build_proof(build_proof, sources, args.native_build, args.compiler, lock)
    verify_sources(lock, sources)
    args.output.mkdir(parents=True)
    assets = {'factory-candidate-erases-data-0x0.bin': factory, 'firmware.bin': blobs['firmware_bin'],
              'bootloader.bin': blobs['bootloader'], 'partitions.bin': blobs['partitions'], 'store.bin': packed,
              contract['sd']['filename']: sd_archive}
    for name, data in assets.items():
        (args.output / name).write_bytes(data)
    report = dict(schema=1, status='software-qualified-candidate-hardware-pending', publication_enabled=False,
                  hardware_tested=False, device_accessed=False, version_reserved_by_recipe=False,
                  factory_erases_data=True, preserving_update_kit_emitted=False,
                  preserving_sdk_migration_eligible=False,
                  preserving_sdk_migration_blocker='Exact deployed bootloader plus candidate boot, health confirmation and rollback are hardware-pending.',
                  input_lock=lock, input_lock_sha256=sha(args.lock.read_bytes()), native=native_proof,
                  build_closure=build_closure, packing=packing, admission=admission, admission_sanitized=admission_sanitized,
                  sd_admission=sd_admission, sd_admission_sanitized=sd_admission_sanitized,
                  sd_unchanged=True, device_msc_sd_workflow_preserved=True,
                  preservation_software_model=preservation, baseline_contract=contract,
                  payload_preservation=payload_preservation,
                  unchanged_store_payloads=len(before) - 6,
                  source_release='test-native-idf61-0.1.122',
                  feed_publication_pending=True,
                  artifacts={name: {'bytes': len(data), 'sha256': sha(data)} for name, data in assets.items()})
    report['feed'] = write_feed(sources, after, packed, blobs['firmware_bin'], args.output)
    verify_packages(package_proof, sources)
    from native_provision_serial import verify_receipts
    startup = verify_receipts(lock, sources)
    for mode, row in startup['runs'].items():
        raw = Path(row['path']).read_bytes()
        require(sha(raw) == row['sha256'], 'Serial startup receipt changed during output')
        (args.output / ('serial-product-' + mode + '.json')).write_bytes(raw)
    (args.output / 'qualification.json').write_bytes(encoded(report))
    (args.output / 'source-lock.json').write_bytes(args.lock.read_bytes())
    (args.output / 'SHA256SUMS').write_text(''.join(sha(path.read_bytes()) + '  ' + path.relative_to(args.output).as_posix() + '\n' for path in sorted(args.output.rglob('*')) if path.is_file() and path != args.output / 'SHA256SUMS'))
    print('Software-qualified candidate; hardware migration remains pending. No publication or device I/O.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('audit-baseline', 'freeze', 'qualify'))
    parser.add_argument('--source', action='append', default=[], metavar='ROLE=CHECKOUT')
    parser.add_argument('--native-build', type=Path)
    parser.add_argument('--compiler', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--sd-archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lock', type=Path)
    parser.add_argument('--candidate-version')
    args = parser.parse_args()
    require(__debug__, 'Do not disable Python assertions')
    sources = parse_sources(args.source)
    if args.operation == 'freeze':
        require(all((args.native_build, args.compiler, args.candidate_version)), 'Freeze requires build, compiler and candidate version')
        freeze(sources, args.native_build.resolve(), args.compiler.resolve(), args.output, args.candidate_version)
    elif args.operation == 'audit-baseline':
        require(args.baseline and not args.output.exists(), 'Baseline required; output must be new')
        contract = json.loads(CONTRACT.read_bytes())
        _, _, files = baseline_bytes(args.baseline, contract, sources)
        sd = released_sd(args.sd_archive, contract, sources['runtime'])
        args.output.write_bytes(encoded(dict(contract_sha256=sha(CONTRACT.read_bytes()), store_files=len(files), elf_count=contract['elf_count'], sd_files=len(sd), sd_elf_count=contract['sd']['elf_count'], private_imports=0, passed=True, hardware_tested=False)))
    else:
        require(all((args.native_build, args.compiler, args.baseline, args.lock, args.sd_archive)), 'Qualify requires build, compiler, baseline, complete SD archive and lock')
        args.native_build = args.native_build.resolve()
        qualify(args, sources)


if __name__ == '__main__':
    main()
