#!/usr/bin/env python3
"""Exercise the native X4 wrapper, rail failures and explicit ready checkpoint."""
import os
import importlib.util
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ['RISCRTE_RUNTIME_ROOT'])
FILES = {
    'esp_attr.h': '#define RTC_NOINIT_ATTR\n#define EXT_RAM_BSS_ATTR __attribute__((section(".ext_ram.bss.test")))\n',
    'esp_heap_caps.h': '#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 1\n#define MALLOC_CAP_8BIT 2\n#define MALLOC_CAP_INTERNAL 4\ninline void* heap_caps_malloc(size_t n,unsigned){return std::malloc(n);}\n',
    'nvs.h': '''#pragma once
#include <cstdint>
#include <cstddef>
using nvs_handle_t=uint32_t;
#define ESP_ERR_NVS_NOT_FOUND 0x1102
#define ESP_ERR_NVS_INVALID_LENGTH 0x110c
#define NVS_READWRITE 1
extern "C" {
int nvs_open(const char*,int,nvs_handle_t*);
int nvs_get_blob(nvs_handle_t,const char*,void*,size_t*);
int nvs_set_blob(nvs_handle_t,const char*,const void*,size_t);
int nvs_commit(nvs_handle_t);
void nvs_close(nvs_handle_t);
}
''',
    'nvs_flash.h': '#pragma once\nextern "C" int nvs_flash_init();\n',
    'esp_system.h': '#pragma once\nint esp_reset_reason();\n',
    'esp_sleep.h': '#pragma once\nint esp_sleep_get_wakeup_cause();\n',
    'esp_timer.h': '#pragma once\n#include <cstdint>\nint64_t esp_timer_get_time();\n',
    'rom/rtc.h': '#pragma once\nint rtc_get_reset_reason(int);\n',
    'soc/gpio_reg.h': '#define GPIO_IN_REG 1\n#define GPIO_IN1_REG 4\n#define GPIO_STRAP_REG 5\n',
    'soc/rtc_cntl_reg.h': '#define RTC_CNTL_PAD_HOLD_REG 2\n#define RTC_CNTL_BROWN_OUT_REG 3\n',
    'soc/soc.h': '#pragma once\n#include <cstdint>\nuint32_t x4_test_reg_read(int);\n#define REG_READ(reg) x4_test_reg_read(reg)\n',
    'X4NativeBuildIdentity.h': '#define X4_NATIVE_COMPOSITION_IDENTITY "X4_NATIVE_COMPOSITION:host-fixture"\n#define X4_NATIVE_SOURCE_IDENTITY "X4_SOURCE=host-fixture"\n',
}
with tempfile.TemporaryDirectory() as name:
    work = Path(name)
    for path, content in FILES.items():
        target = work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    binary = work / 'native-boot-test'
    args = [os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', '-DRISC_NATIVE_ESP_IDF=1',
            '-DCONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY=1', '-DCONFIG_SPIRAM_BOOT_INIT=1', '-I' + str(work),
            '-I' + str(ROOT / 'minimal/test/early_native_fake'), '-I' + str(RUNTIME / 'sdk/driver'),
            str(ROOT / 'minimal/test/native_idf61_boot_test.cpp'), '-o', str(binary)]
    if os.environ.get('SANITIZE') == '1':
        args[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
    subprocess.run(args, check=True)
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    cases = 0
    for held in (0, 1, 2, 3):
        for mux in (0, 1):
            for failure in range(9):
                subprocess.run([str(binary), str(failure), str(held), str(mux)], check=True,
                               env=env, stdout=subprocess.DEVNULL)
                cases += 1
    for mode in ('reset', 'milestone'):
        subprocess.run([str(binary), mode], check=True, env=env)
    saved = work / 'native-ready.bin'
    subprocess.run([str(binary), 'checkpoint', str(saved)], check=True, env=env)
    spec = importlib.util.spec_from_file_location('recover', ROOT / 'minimal/scripts/recover_bootlog.py')
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
    recovered = recovery.recover(saved.read_bytes())
    assert len(recovered) == 1 and recovered[0]['phase'] == 'native-ready'
    assert recovered[0]['variant_us'] > recovered[0]['entry_us'] and recovered[0]['gate_us'] == 0
print(f'Native IDF rail/startup: {cases} hold/mux/failure cases, ready ordering/idempotence, reset and diagnostics PASS')
