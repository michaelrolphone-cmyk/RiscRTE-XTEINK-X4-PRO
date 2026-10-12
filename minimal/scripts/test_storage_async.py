#!/usr/bin/env python3
"""Test the production X4 provider against the shared StorageFatFs implementation."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from prepare_sdk import prepare
from prepare_sd_wire_fixture import prepare as prepare_wire_fixture

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
for name in ('runtime', 'drivers', 'reference-reader', 'output'):
    p.add_argument('--' + name, type=lambda x: Path(x).resolve(), required=True)
p.add_argument('--target-cc', help='Also compile the admission/FatFs fixture for Xtensa (no device execution)')
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
sdk = a.output / 'sdk'
if sdk.exists():
    shutil.rmtree(sdk)
prepare(a.runtime, a.reference_reader, sdk)
for source in (a.runtime / 'sdk/app').glob('*.h'):
    target = sdk / source.name
    if target.exists() and target.read_bytes() != source.read_bytes():
        raise ValueError('Conflicting SDK header: ' + source.name)
    shutil.copyfile(source, target)
storage = a.drivers / 'lib/StorageFatFs'
prepare_wire_fixture(sdk)
for test in ('sd_async_test', 'sd_session_admission_test'):
    binary = a.output / test
    subprocess.run(['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-overflow',
                *(['-fsanitize=undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer'] if os.environ.get('SANITIZE')=='1' else []), '-DX4PRO_SD_ALLOW_LEGACY_GPIO=1', '-I' + str(sdk), '-I' + str(storage),
                '-I' + str(a.reference_reader / 'Drivers/x4pro_board'), '-I' + str(a.reference_reader),
                str(ROOT / 'minimal/test' / (test + '.c')), str(storage / 'fatfs/ff.c'),
                str(storage / 'fatfs/ffunicode.c'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    if test == 'sd_session_admission_test':
        for scenario in ('retained-writer', 'retained-unlock'):
            subprocess.run([str(binary), scenario], check=True)
if a.target_cc:
    subprocess.run([a.target_cc, '-std=c11', '-O2', '-fno-ivopts', '-fPIC',
                    '-mtext-section-literals', '-mlongcalls', '-Wall', '-Wextra',
                    '-Werror', '-Wno-overflow', '-DX4PRO_SD_ALLOW_LEGACY_GPIO=1',
                    '-I' + str(sdk), '-I' + str(storage),
                    '-I' + str(a.reference_reader / 'Drivers/x4pro_board'),
                    '-I' + str(a.reference_reader), '-c',
                    str(ROOT / 'minimal/test/sd_session_admission_test.c'),
                    '-o', str(a.output / 'sd_session_admission_test.xtensa.o')], check=True)
    print('Warm admission Xtensa fixture compile and append-only ABI assertions PASS')
