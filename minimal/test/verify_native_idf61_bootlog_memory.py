#!/usr/bin/env python3
"""Prove X4 bootlog copy placement in an SDK6.1 Xtensa object or final ELF.

This supplements the unchanged Runtime radio_iq_proof and X4 startup proof.
An object result never establishes the final IQ bank or startup call edges.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile

COPIES = {
    '_ZN9X4BootLog12_GLOBAL__N_1L7historyE': 3648,
    '_ZN9X4BootLog12_GLOBAL__N_1L7currentE': 456,
    '_ZN12_GLOBAL__N_1L8previousE': 264,
    '_ZN9X4BootLog12_GLOBAL__N_1L11earlyEventsE': 160,
}
CONTROLS = (
    '_ZN12_GLOBAL__N_1L12startupErrorE',
    '_ZN12_GLOBAL__N_1L9attemptedE',
    '_ZN12_GLOBAL__N_1L7variantE',
    '_ZN12_GLOBAL__N_1L8reportedE',
    '_ZN12_GLOBAL__N_1L13previousValidE',
    '_ZN9X4BootLog12_GLOBAL__N_1L6handleE',
    '_ZN9X4BootLog12_GLOBAL__N_1L9availableE',
    '_ZN9X4BootLog12_GLOBAL__N_1L11initializedE',
    '_ZN9X4BootLog12_GLOBAL__N_1L7pendingE',
    '_ZN9X4BootLog12_GLOBAL__N_1L11insideDrainE',
    '_ZN9X4BootLog12_GLOBAL__N_1L13fileUncertainE',
    '_ZN9X4BootLog12_GLOBAL__N_1L10earlyCountE',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _object_startup(elf):
    """Check the actual relocation-backed CALLX8 sequence in the target object."""
    code = elf.get_section_by_name('.text.__wrap_app_main')
    relocations = elf.get_section_by_name('.rela.text.__wrap_app_main')
    require(code is not None and relocations is not None, 'Missing object startup code/relocations')
    symbols = elf.get_section(relocations['sh_link'])
    calls = []
    for relocation in relocations.iter_relocations():
        if relocation['r_info_type'] != 11:  # R_XTENSA_ASM_EXPAND (pinned Xtensa toolchain)
            continue
        target = symbols.get_symbol(relocation['r_info_sym'])
        name = target.name
        if not name and isinstance(target['st_shndx'], int):
            name = elf.get_section(target['st_shndx']).name
        name = name.removeprefix('.text.')
        offset = relocation['r_offset']
        # Pinned windowed ABI expands the call to literal-load a8; CALLX8 a8.
        require(code.data()[offset:offset + 1] == b'\x81' and
                code.data()[offset + 3:offset + 6] == b'\xe0\x08\x00',
                'Relocation is not an actual startup CALLX8: ' + name)
        calls.append({'instruction': offset + 3, 'target': name})
    calls.sort(key=lambda call: call['instruction'])
    required = ['gpio_set_level', '_ZL16stageDigitalRailv', 'rtc_gpio_deinit',
                'gpio_set_level', 'gpio_get_level', 'gpio_hold_dis',
                'gpio_hold_en', 'gpio_get_level']
    watched = set(required) | {'gpio_config', 'rtc_gpio_isolate'}
    rail = [call for call in calls if call['target'] in watched]
    require([call['target'] for call in rail] == required, 'Changed object GPIO1 handoff order')
    def one(prefix):
        found = [call for call in calls if call['target'].startswith(prefix)]
        require(len(found) == 1, 'Missing/ambiguous startup call: ' + prefix)
        return found[0]
    storage = one('_ZN9X4BootLog12_GLOBAL__N_1L5startERKN6X4Boot6RecordE')
    ready = one('risc_x4_native_ready')
    runtime = one('__real_app_main')
    require(rail[-1]['instruction'] < storage['instruction'] < ready['instruction'] < runtime['instruction'],
            'Bootlog/ready/Runtime object ordering changed')
    early = [call for call in calls if call['target'] == '_ZN9X4BootLog12_GLOBAL__N_1L5earlyEPKci']
    require(len(early) == 8 and all(call['instruction'] < storage['instruction'] for call in early),
            'Early rail evidence capture changed')
    return {'gpio1_handoff_calls': rail, 'bootlog_start': storage,
            'native_ready': ready, 'runtime_entry': runtime, 'early_event_calls': early}


def proof(elf_bytes):
    elf = ELFFile(io.BytesIO(elf_bytes))
    require(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_XTENSA',
            'Expected ELF32 little-endian Xtensa')
    require(elf['e_type'] in ('ET_REL', 'ET_EXEC'), 'Expected object or final executable')
    final = elf['e_type'] == 'ET_EXEC'
    symtab = elf.get_section_by_name('.symtab')
    require(symtab is not None, 'Missing symbol table')
    symbols = {symbol.name: symbol for symbol in symtab.iter_symbols()}
    def located(name):
        symbol = symbols.get(name)
        require(symbol is not None and isinstance(symbol['st_shndx'], int) and symbol['st_size'] > 0,
                'Missing allocated symbol: ' + name)
        require(symbol['st_info']['type'] == 'STT_OBJECT', 'Expected data object: ' + name)
        section = elf.get_section(symbol['st_shndx'])
        require(section['sh_flags'] & 3 == 3, 'Data object is not writable/allocated: ' + name)
        offset = symbol['st_value'] - section['sh_addr']
        require(0 <= offset < offset + symbol['st_size'] <= section['sh_size'],
                'Data object exceeds its section: ' + name)
        return symbol, section
    copies = {}
    for name, expected_bytes in COPIES.items():
        symbol, section = located(name)
        require(symbol['st_size'] == expected_bytes, 'Changed copy capacity: ' + name)
        require(section.name == '.ext_ram.bss' or section.name.startswith('.ext_ram.bss.'),
                'Bootlog copy is not external BSS: ' + name)
        require(section['sh_addralign'] >= 8 and symbol['st_value'] % 8 == 0,
                'Bootlog copy alignment changed: ' + name)
        if final:
            require(section['sh_type'] == 'SHT_NOBITS', 'External BSS is not NOLOAD: ' + name)
            require(0x3C000000 <= symbol['st_value'] < symbol['st_value'] + symbol['st_size'] <= 0x3E000000,
                    'Bootlog copy is outside S3 external address range: ' + name)
        elif section['sh_type'] != 'SHT_NOBITS':
            start = symbol['st_value'] - section['sh_addr']
            require(not any(section.data()[start:start + expected_bytes]),
                    'Nonzero initialized bytes would be lost in NOLOAD: ' + name)
        copies[name] = {'section': section.name, 'address': symbol['st_value'], 'bytes': expected_bytes}
    controls = {}
    for name in CONTROLS:
        symbol, section = located(name)
        if final:
            require(section.name in ('.dram0.bss', '.dram0.data') and
                    0x3FC88000 <= symbol['st_value'] < symbol['st_value'] + symbol['st_size'] <= 0x3FD00000,
                    'Boot/persistence control is not internal DRAM: ' + name)
        else:
            require(section.name.startswith(('.bss.', '.data.', '.dram1.')),
                    'Boot/persistence control is not internal: ' + name)
        controls[name] = {'section': section.name, 'address': symbol['st_value'], 'bytes': symbol['st_size']}
    rtc, rtc_section = located('risc_x4_boot_record')
    require(rtc['st_size'] == 264 and (rtc_section.name == '.rtc_noinit' or rtc_section.name.startswith('.rtc_noinit.')),
            'RTC boot evidence placement/layout changed')
    require(not any(name.startswith('_GLOBAL__sub_I_') and ('risc_x4_' in name or 'X4EarlyBoot' in name)
                    for name in symbols), 'X4 global constructor accesses bootlog state')
    if not final:
        require(not any(section.name.startswith(('.init_array', '.ctors')) and section['sh_size']
                        for section in elf.iter_sections()), 'Object has a pre-app-main constructor')
    return {'schema': 'x4.native-idf61-bootlog-memory-proof', 'schema_version': 1,
            'elf_sha256': hashlib.sha256(elf_bytes).hexdigest(), 'input_kind': 'final-elf' if final else 'target-object',
            'copied_bytes_external': sum(COPIES.values()), 'copies': copies, 'internal_controls': controls,
            'rtc_record_bytes': rtc['st_size'], 'global_constructor': False,
            'object_startup_order': None if final else _object_startup(elf),
            'startup_authority': 'Pair with verify_native_idf61_target.py final linked startup proof',
            'iq_bank_verified': False, 'iq_authority': 'Unchanged Runtime scripts/radio_iq_proof.py',
            'predicted_margin_from_failed_x4_elf_bytes': 96,
            'hardware_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(proof(args.elf.read_bytes()), indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end='')


if __name__ == '__main__':
    main()
