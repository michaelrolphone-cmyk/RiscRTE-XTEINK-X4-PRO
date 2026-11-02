#!/usr/bin/env python3
"""Fresh shared Home X4 native dependency, using the existing controlled IDF build."""
from native_idf61_build import *
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', default=[])
    for name in ('compiler', 'native-build', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('controlled_product_recipe', root / 'scripts/native_idf61_candidate.py')
    recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)
    sources = {}
    for row in args.source:
        role, value = row.split('=', 1)
        require(role not in sources, 'Duplicate source role')
        sources[role] = Path(value).resolve()
    require(set(sources)=={'product','runtime','sdk'}, 'Exact product/runtime/SDK source closure required')
    build, output, compiler = args.native_build.resolve(), args.output.resolve(), args.compiler.resolve()
    validate_layout(sources, build, output, root)
    pins = {role: recipe.clean_source(path, recipe.git(path, 'rev-parse', 'HEAD').decode().strip()) for role, path in sources.items()}
    require(pins['sdk']['revision'] == recipe.SDK_REVISION, 'Unreviewed SDK source')
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
    commands = build_commands(sources, build, pins['runtime']['revision'], cmake)
    commands[0] = [value.replace('/profiles/native-idf61.cmake','/profiles/native-shared-home.cmake') for value in commands[0]]
    build.parent.mkdir(parents=True, exist_ok=True)
    for command in commands:
        subprocess.run(command, env=env, check=True)
    proof = collect_build_proof(recipe, sources, build, compiler, pins, commands, env, tools)
    validate_build_proof(proof, sources, build, compiler)
    from elftools.elf.elffile import ELFFile
    import io
    paths=recipe.artifact_paths(build)
    raw=(build/paths['firmware_elf']).read_bytes()
    elf=ELFFile(io.BytesIO(raw))
    require(elf.elfclass==32 and elf.little_endian and elf['e_machine']=='EM_XTENSA','Wrong native ELF')
    symbols={s.name:s for s in elf.get_section_by_name('.symtab').iter_symbols()}
    for name, expected in (('risc_app_policy_rows',b'RISC_APP_POLICY_ROWS:32\0'),
                           ('risc_app_requirement_rows',b'RISC_APP_REQUIREMENT_ROWS:32\0')):
        symbol=symbols.get(name)
        require(symbol is not None and symbol['st_info']['bind']=='STB_GLOBAL' and isinstance(symbol['st_shndx'],int),'Missing strong native capacity symbol')
        section=elf.get_section(symbol['st_shndx'])
        offset=symbol['st_value']-section['sh_addr']
        require(section['sh_flags']&2 and section.data()[offset:offset+symbol['st_size']]==expected,'Compiled capacity differs')
    output.mkdir(parents=True)
    for role,path in paths.items():
        target=output/path
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(build/path,target)
    receipt=dict(schema=1,hardware_tested=False,factory_image=False,
      scope='Fresh complete X4 native firmware dependency; full 0.1.123 features, 32 policy/requirement rows. Boot-store/app cohort assembly is separate.',
      sources=pins,commands=commands,compiler=tools,artifacts=proof.artifacts,
      build_closure_sha256=sha((build/'native-build-evidence/build-closure.json').read_bytes()))
    (output/'qualification.json').write_bytes(recipe.encoded(receipt))
    shutil.copytree(build/'native-build-evidence',output/'native-build-evidence')
    print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':
    main()
