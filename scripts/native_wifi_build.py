#!/usr/bin/env python3
"""Build isolated X4 native Wi-Fi profile and collect source/resource evidence.
No packaging, deployment, legacy recipe mutation or storage/capacity approval.
"""
from native_idf61_build import *
RUNTIME='4a04f85223d87d54fc6b9defb3ef4453b4fcc690'

def resources(build,compiler,env,profile,root):
    from elftools.elf.elffile import ELFFile
    rows=json.loads((build/'compile_commands.json').read_text())
    runtime=[r for r in rows if r['file'].endswith('/src/bootstrap/Runtime.cpp')]
    require(len(runtime)==1,'Ambiguous actual Runtime compilation')
    argv=runtime[0].get('arguments') or shlex.split(runtime[0]['command'])
    expected=root/('profiles/native-wifi-settings.h' if profile=='successor' else 'profiles/native-idf61-settings.h')
    require(any(argv[i]=='-include' and Path(argv[i+1]).resolve()==expected for i in range(len(argv)-1)),'Actual Runtime uses different settings header')
    flags=[v for v in argv if v.startswith('-DRISC_RUNTIME_PREFERENCE_STORE=')]
    require(flags==(['-DRISC_RUNTIME_PREFERENCE_STORE=1'] if profile=='successor' else []),'Actual Runtime preferences selection differs')
    with (build/'riscrte_native.elf').open('rb') as f:
        elf=ELFFile(f)
        require(elf.elfclass==32 and elf.little_endian and elf['e_machine']=='EM_XTENSA','Not actual Xtensa native ELF')
        sections={s.name:int(s['sh_size']) for s in elf.iter_sections() if s['sh_flags']&2}
        addresses={s.name:{'address':int(s['sh_addr']),'bytes':int(s['sh_size'])} for s in elf.iter_sections() if s['sh_flags']&2}
        symbols=[{'name':s.name,'address':int(s['st_value']),'bytes':int(s['st_size']),'section':elf.get_section(s['st_shndx']).name} for s in elf.get_section_by_name('.symtab').iter_symbols() if isinstance(s['st_shndx'],int) and s['st_size']]
    usage=[]
    for p in sorted(build.rglob('*.su')):
        usage.append({'path':str(p.relative_to(build)),**file_row(p)})
    require(usage,'Actual stack-usage files absent')
    config=json.loads((build/'config/sdkconfig.json').read_text())
    return {'firmware_bytes':(build/'riscrte_native.bin').stat().st_size if (build/'riscrte_native.bin').is_file() else None,'allocated_sections':sections,'section_addresses':addresses,'internal_bss_symbols':sorted([x for x in symbols if x['section']=='.dram0.bss'],key=lambda x:(-x['bytes'],x['name'])),'allocator_config':{k:v for k,v in config.items() if any(tag in k for tag in ('SPIRAM','HEAP_POISON','HEAP_TASK_TRACKING','MEMPROT'))},'largest_symbols':sorted(symbols,key=lambda x:(-x['bytes'],x['name']))[:100],'stack_usage_files':usage,'heap_peak':'not measured','task_stack_high_water':'not measured','allocator_overhead':'not measured','fits_product_runtime_budget':'not established'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('previous','successor'), required=True)
    for name in ('compiler', 'runtime', 'sdk', 'native-build', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('controlled_product_recipe', root / 'scripts/native_idf61_candidate.py')
    recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)
    sources = {'product':root.resolve(),'runtime':args.runtime.resolve(),'sdk':args.sdk.resolve()}
    build, output, compiler = args.native_build.resolve(), args.output.resolve(), args.compiler.resolve()
    validate_layout(sources, build, output, root)
    pins = {role: recipe.clean_source(path, recipe.git(path, 'rev-parse', 'HEAD').decode().strip()) for role, path in sources.items()}
    require(pins['sdk']['revision'] == recipe.SDK_REVISION, 'Unreviewed SDK source')
    require(pins['runtime']['revision']==RUNTIME, 'Unreviewed Runtime source')
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
    selected='native-wifi.cmake' if args.profile=='successor' else 'native-provision-123.cmake'
    commands[0]=[v.replace('/profiles/native-idf61.cmake','/profiles/'+selected) for v in commands[0]]
    build.parent.mkdir(parents=True, exist_ok=True)
    try:
        for command in commands:
            subprocess.run(command, env=env, check=True)
    except subprocess.CalledProcessError:
        # A post-link guard may reject an existing ELF. Measure it, never certify it.
        if (build/'riscrte_native.elf').is_file() and (build/'compile_commands.json').is_file():
            output.mkdir()
            measured=resources(build,compiler,env,args.profile,root)
            for role,path in sources.items():
                require(recipe.clean_source(path,pins[role]['revision'])==pins[role],'Source changed during failed build')
            rejected={'schema':1,'product':'x4','status':'build_rejected','scope':'diagnostic rejected ELF only','full_firmware_linked':False,'native_qualified':False,'runtime_commit':RUNTIME,'product_commit':pins['product']['revision'],'selected_profile':'profiles/'+selected,'sources':pins,'resources':measured,'artifacts':{n:file_row(build/n) for n in ('riscrte_native.elf','riscrte_native.map') if (build/n).is_file()},'persistent_storage_preservation':'not qualified','resource_budget':'not qualified'}
            (output/'rejected-build-measurement.json').write_bytes(recipe.encoded(rejected))
            print('REJECTED NATIVE MEASUREMENT '+json.dumps(rejected,sort_keys=True),flush=True)
        raise
    subprocess.run([sys.executable,str(sources['runtime']/'test/native_firmware_idf6_test.py'),'--build',str(build)],env=env,check=True)
    proof = collect_build_proof(recipe, sources, build, compiler, pins, commands, env, tools)

    validate_build_proof(proof,sources,build,compiler)
    measured=resources(build,compiler,env,args.profile,root)
    output.mkdir()
    receipt={'schema':1,'product':'x4','status':'linked_boundary_passed','scope':'fresh-linked-native-build-measurement','full_firmware_linked':True,'product_commit':pins['product']['revision'],'runtime_commit':RUNTIME,'sdk_commit':pins['sdk']['revision'],'working_tree_dirty':False,'selected_profile':'profiles/'+selected,'sources':pins,'artifacts':proof.artifacts,'resources':measured,'physical_testing':False,'deployment':False,'persistent_storage_preservation':'not qualified','resource_budget':'not qualified','companion_store_admission':'not qualified'}
    (output/'build-receipt.json').write_bytes(recipe.encoded(receipt))
    (output/'build-closure.json').write_bytes(recipe.encoded(proof.report))
    print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':main()
