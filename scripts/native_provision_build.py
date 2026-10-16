#!/usr/bin/env python3
"""Fresh source-pinned .123 packages/native build and same-process qualification.

The .122 producer is reused only for generic dependency/command custody. Its
recipe, profile, release manifest and artifacts remain immutable.
"""
from native_idf61_build import *

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', default=[])
    for name in ('compiler', 'baseline', 'native-build', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--candidate-version', required=True)
    parser.add_argument('--sd-archive', type=Path, required=True)
    parser.add_argument('--home-compiler', type=Path, required=True)
    parser.add_argument('--serial-product-normal', type=Path, required=True)
    parser.add_argument('--serial-product-sanitized', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('controlled_product_recipe', root / 'scripts/native_provision_candidate.py')
    recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)
    sources = recipe.parse_sources(args.source)
    build, output, compiler = args.native_build.resolve(), args.output.resolve(), args.compiler.resolve()
    validate_layout(sources, build, output, root)
    pins = {role: recipe.clean_source(path, recipe.git(path, 'rev-parse', 'HEAD').decode().strip()) for role, path in sources.items()}
    require(pins['sdk']['revision'] == recipe.SDK_REVISION, 'Unreviewed SDK source')
    from native_provision_serial import read_receipts
    serial_product_tests = read_receipts(sources['runtime'], args.serial_product_normal, args.serial_product_sanitized)
    version = run([compiler, '--version']).splitlines()[0]
    require('15.2.0' in version and 'esp-15.2.0_20251204' in version, 'Exact native GCC15 required')
    env = clean_environment(sources['sdk'], compiler)
    cmake = shutil.which('cmake', path=env['PATH'])
    require(cmake is not None, 'Native CMake missing')
    cmake = Path(cmake).resolve()
    if cmake.read_bytes()[:2] == b'#!':
        native_cmake = cmake.parent.parent / 'cmake/data/bin/cmake'
        require(native_cmake.is_file() and native_cmake.read_bytes()[:4] == b'\x7fELF', 'Use native CMake or an isolated IDF environment; ambient PYTHONPATH is not allowed')
        cmake = native_cmake.resolve()
    env['PATH'] = str(cmake.parent) + os.pathsep + env['PATH']
    tools = compiler_family(compiler)
    selected_tools = [('gcc', str(compiler)), ('g++', str(compiler.with_name('xtensa-esp-elf-g++'))),
                             ('python', sys.executable), ('cmake', str(cmake)),
                             ('ninja', shutil.which('ninja', path=env['PATH']))]
    selected_tools.extend((name, str(compiler.with_name('xtensa-esp-elf-' + name))) for name in ('as', 'ld', 'ar', 'objcopy', 'objdump', 'readelf', 'nm', 'c++filt'))
    for name in ('cc1', 'cc1plus', 'collect2'):
        executable = compiler_child(compiler, name, env)
        selected_tools.append((name, executable))
    for name, executable in selected_tools:
        require(executable is not None and Path(executable).is_file(), 'Required native build tool missing: ' + name)
        path = Path(executable).resolve(); tools[name] = {'path': str(path), **file_row(path)}
    from native_provision_payloads import build_packages
    package_proof = build_packages(sources, build.parent / (build.name + '-packages'),
                                   args.home_compiler.resolve(), compiler.with_name('xtensa-esp32s3-elf-gcc'))
    commands = build_commands(sources, build, pins['runtime']['revision'], cmake)
    commands[0] = [value.replace('/profiles/native-idf61.cmake', '/profiles/native-provision-123.cmake') for value in commands[0]]
    build.parent.mkdir(parents=True, exist_ok=True)
    for command in commands:
        subprocess.run(command, env=env, check=True)
    # These two bounded probes reuse the completed product's exact target flags.
    # Preserve their objects and receipt before freezing controlled build evidence.
    subprocess.run([sys.executable, str(sources['runtime'] / 'test/compile_runtime_platform_capacity_target.py'),
                    str(build / 'compile_commands.json'), str(build / 'platform-capacity-probe')], env=env, check=True)
    proof = collect_build_proof(recipe, sources, build, compiler, pins, commands, env, tools)
    args.native_build, args.compiler, args.output = build, compiler, output
    args.lock = build / 'native-build-evidence/source-lock.json'
    lock = recipe.freeze(sources, build, compiler, args.lock, args.candidate_version)
    lock['package_build'] = package_proof.receipt
    lock['serial_product_tests'] = serial_product_tests
    args.lock.write_bytes(recipe.encoded(lock))
    validate_build_proof(proof, sources, build, compiler, json.loads(args.lock.read_bytes()))
    recipe.qualify(args, sources, build_proof=proof, package_proof=package_proof)


if __name__ == '__main__':
    main()
