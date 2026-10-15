#!/usr/bin/env python3
"""Test the proof checker on a small synthetic Xtensa ELF, never a firmware build."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--selection', type=Path, required=True)
a = p.parse_args()
selection = dict(line.split('=', 1) for line in a.selection.read_text().splitlines())
with tempfile.TemporaryDirectory() as name:
    work = Path(name)
    source = r'''
extern "C" {
int gpio_set_level(int,int); int rtc_gpio_deinit(int); int gpio_get_level(int);
int gpio_hold_dis(int); int gpio_hold_en(int);
void risc_x4_native_ready(); const char* risc_native_startup_error();
void risc_native_diagnostic_observer(const char*); void risc_native_diagnostic_drain();
void risc_native_diagnostic_read(); void risc_native_diagnostic_read_after();
void app_main();
__attribute__((section(".rtc_noinit"))) unsigned risc_x4_boot_record[66];
extern const char risc_x4_native_composition_identity[]="X4_NATIVE_COMPOSITION:@COMPOSITION@";
extern const char risc_x4_native_source_identity[]="X4_SOURCE=@PRODUCT@";
extern const char runtime_source[]="RTE_SOURCE=@RUNTIME@";
volatile unsigned counter=0;
}
static __attribute__((noinline,noipa)) int stageDigitalRail(){counter=1;return counter;}
extern "C" __attribute__((noinline,noipa)) void __wrap_app_main(){
 gpio_set_level(1,1);stageDigitalRail();rtc_gpio_deinit(1);gpio_set_level(1,1);
 gpio_get_level(1);gpio_hold_dis(1);gpio_hold_en(1);gpio_get_level(1);
 risc_x4_native_ready();app_main();
}
extern "C" __attribute__((noinline,noipa)) void main_task(){__wrap_app_main();}
__attribute__((noinline,noipa)) void setup(){risc_native_startup_error();}
namespace RiscDiagnostics {__attribute__((noinline,noipa)) void line(const char* s){risc_native_diagnostic_observer(s);}}
'''.replace('@COMPOSITION@', selection['composition_sha256']).replace('@PRODUCT@', selection['product_source']).replace('@RUNTIME@', selection['runtime_source'])
    (work / 'entry.cpp').write_text(source)
    (work / 'stubs.cpp').write_text('''extern "C" {
extern volatile unsigned counter;
int gpio_set_level(int,int){return ++counter;} int rtc_gpio_deinit(int){return ++counter;}
int gpio_get_level(int){return ++counter;} int gpio_hold_dis(int){return ++counter;}
int gpio_hold_en(int){return ++counter;} void risc_x4_native_ready(){++counter;}
const char* risc_native_startup_error(){++counter;return 0;}
void risc_native_diagnostic_observer(const char*){++counter;}
void risc_native_diagnostic_drain(){++counter;} void risc_native_diagnostic_read(){++counter;}
void risc_native_diagnostic_read_after(){++counter;} void app_main(){++counter;}
}
''')
    (work / 'fixture.ld').write_text('''ENTRY(main_task)
SECTIONS {
 . = 0x42000000; .text : { *(.literal*) *(.text*) }
 .rodata : { *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) }
 .rtc_noinit 0x50000000 (NOLOAD) : { *(.rtc_noinit) }
}
''')
    compiler = os.environ.get('X4_NATIVE_CXX', 'xtensa-esp32s3-elf-g++')
    for item in ('entry', 'stubs'):
        subprocess.run([compiler, '-std=c++17', '-Os', '-mlongcalls', '-fno-exceptions', '-fno-rtti',
                        '-ffunction-sections', '-fdata-sections', '-c', str(work / (item + '.cpp')),
                        '-o', str(work / (item + '.o'))], check=True)
    subprocess.run([compiler, '-nostdlib', '-Wl,-T,' + str(work / 'fixture.ld'),
                    str(work / 'entry.o'), str(work / 'stubs.o'), '-o', str(work / 'fixture.elf')], check=True)
    subprocess.run(['python3', str(ROOT / 'minimal/test/verify_native_idf61_target.py'),
                    '--elf', str(work / 'fixture.elf'), '--selection', str(a.selection.resolve()),
                    '--output', str(work / 'proof.json')], check=True)
    result = json.loads((work / 'proof.json').read_text())
    assert len(result['bypass_mutations_rejected']) == 5
print('Synthetic Xtensa proof fixture and five bypass mutations PASS; not a product linked-image qualification')
