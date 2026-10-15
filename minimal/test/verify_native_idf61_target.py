#!/usr/bin/env python3
"""Verify final native-IDF Xtensa startup edges and reject bypass mutations.

This consumes a newly linked candidate ELF; an object compile is not this proof.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('x4_released_proof', ROOT / 'minimal/scripts/prepare_native_runtime.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def proof(data, selection):
    elf = ELFFile(io.BytesIO(data))
    c.require(elf['e_machine'] == 'EM_XTENSA' and elf['e_type'] == 'ET_EXEC', 'Final linked Xtensa ELF required')
    symbols = {s.name: s for s in elf.get_section_by_name('.symtab').iter_symbols()}
    names = ('__wrap_app_main', 'app_main', 'risc_x4_native_ready', 'risc_x4_boot_record',
             'risc_native_startup_error', 'risc_native_diagnostic_observer', 'risc_native_diagnostic_drain',
             'risc_native_diagnostic_read', 'risc_native_diagnostic_read_after',
             'risc_x4_native_composition_identity', 'risc_x4_native_source_identity')
    for name in names:
        symbol = symbols.get(name)
        c.require(symbol is not None and isinstance(symbol['st_shndx'], int) and
                  symbol['st_info']['bind'] == 'STB_GLOBAL', 'Missing strong native X4 symbol: ' + name)
    for name in ('initArduino', 'initVariant'):
        c.require(name not in symbols or symbols[name]['st_shndx'] == 'SHN_UNDEF',
                  'Arduino checkpoint still linked: ' + name)
    marker = ('X4_NATIVE_COMPOSITION:' + selection['composition_sha256']).encode() + b'\0'
    c.require(c.elf_symbol_bytes(elf, symbols['risc_x4_native_composition_identity']) == marker,
              'Candidate composition marker differs from selection')
    source = c.elf_symbol_bytes(elf, symbols['risc_x4_native_source_identity'])
    c.require(('X4_SOURCE=' + selection['product_source']).encode() in source, 'Product source marker differs')
    c.require(('RTE_SOURCE=' + selection['runtime_source']).encode() + b'\0' in data, 'Runtime source marker differs')
    edges = [('main_task', '__wrap_app_main'), ('__wrap_app_main', 'risc_x4_native_ready'),
             ('__wrap_app_main', 'app_main'), ('_Z5setupv', 'risc_native_startup_error'),
             ('_ZN15RiscDiagnostics4lineEPKc', 'risc_native_diagnostic_observer')]
    linked = {}
    for caller, callee in edges:
        c.require(callee in symbols, 'Missing startup target: ' + callee)
        matches = [edge for edge in c.xtensa_calls(elf, symbols, caller)
                   if edge['target'] == symbols[callee]['st_value']]
        c.require(len(matches) == 1, 'Unproven native X4 call: ' + caller + ' -> ' + callee)
        linked[caller + ' -> ' + callee] = matches[0]
    c.require(not any(edge['target'] == symbols['app_main']['st_value']
                      for edge in c.xtensa_calls(elf, symbols, 'main_task')), 'IDF task bypasses X4 wrapper')
    stage = '_ZL16stageDigitalRailv'
    required = ['gpio_set_level', stage, 'rtc_gpio_deinit', 'gpio_set_level',
                'gpio_get_level', 'gpio_hold_dis', 'gpio_hold_en', 'gpio_get_level']
    c.require(all(name in symbols for name in required), 'Missing staged GPIO1 function')
    watched = {symbols[name]['st_value']: name for name in required}
    watched.update({symbols[name]['st_value']: name for name in ('gpio_config', 'rtc_gpio_isolate') if name in symbols})
    rail = [dict(edge, target_name=watched[edge['target']])
            for edge in c.xtensa_calls(elf, symbols, '__wrap_app_main') if edge['target'] in watched]
    c.require([edge['target_name'] for edge in rail] == required, 'GPIO1 ordered staged handoff not proven')
    c.require(not any(instruction[2].startswith('call') for instruction in c.xtensa_instructions(elf, symbols[stage])),
              'GPIO1 staging contains nested calls')
    ready = linked['__wrap_app_main -> risc_x4_native_ready']['instruction']
    runtime = linked['__wrap_app_main -> app_main']['instruction']
    c.require(rail[-1]['instruction'] < ready < runtime, 'Ready checkpoint is outside the rail/Runtime boundary')
    rtc = symbols['risc_x4_boot_record']
    c.require(elf.get_section(rtc['st_shndx']).name == '.rtc_noinit' and rtc['st_size'] == 264,
              'RTC no-init record layout changed')
    return {'schema': 'x4.native-idf61-startup-proof', 'schema_version': 1,
            'composition_sha256': selection['composition_sha256'],
            'elf_sha256': hashlib.sha256(data).hexdigest(), 'required_strong_symbols': names,
            'target_call_edges': linked, 'gpio1_handoff_call_order': rail,
            'rtc_record_bytes': 264, 'native_ready_checkpoint': 'risc_x4_native_ready',
            'earliest_scope': 'app_main entry after IDF hardware, cores and PSRAM startup',
            'hardware_qualified': False, 'historical_replay': False}


def mutate_edge(data, edge):
    elf = ELFFile(io.BytesIO(data))
    address = edge.get('literal', edge['instruction'])
    size = 4 if 'literal' in edge else 3
    for section in elf.iter_sections():
        if section['sh_type'] != 'SHT_NOBITS' and section['sh_addr'] <= address and address + size <= section['sh_addr'] + section['sh_size']:
            offset = section['sh_offset'] + address - section['sh_addr']
            altered = bytearray(data)
            altered[offset:offset + size] = bytes(size)
            return bytes(altered)
    raise ValueError('Call mutation address is outside file-backed ELF sections')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--objdump', default=shutil.which('xtensa-esp32s3-elf-objdump'))
    a = p.parse_args()
    c.require(a.objdump, 'SDK 6.1 Xtensa objdump required')
    version = subprocess.check_output([a.objdump, '--version'], text=True).splitlines()[0]
    c.require(version == 'GNU objdump (crosstool-NG esp-15.2.0_20251204) 2.45', 'SDK 6.1 pinned objdump required')
    # Reuse the released byte-boundary CALL8/CALLX8 decoder, with the new pinned tool.
    c.xtensa_objdump = lambda: a.objdump
    text = a.selection.read_text()
    payload, digest = text.rsplit('composition_sha256=', 1)
    c.require(hashlib.sha256(payload.encode()).hexdigest() == digest.strip(), 'Invalid selection digest')
    selection = dict(line.split('=', 1) for line in text.splitlines())
    c.require(selection['schema'] == 'x4.native-idf61-selection-v1', 'Wrong selection schema')
    data = a.elf.read_bytes()
    result = proof(data, selection)
    rejected = []
    for name, edge in result['target_call_edges'].items():
        try:
            proof(mutate_edge(data, edge), selection)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError('Startup/observer bypass mutation admitted: ' + name)
    result['bypass_mutations_rejected'] = rejected
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print('X4 native-IDF final ELF startup/ready/gate/observer/RTC proof and bypass rejection PASS')


if __name__ == '__main__':
    main()
