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
binary = a.output / 'test'
subprocess.run(['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-overflow',
                *(['-fsanitize=undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer'] if os.environ.get('SANITIZE')=='1' else []), '-DX4PRO_SD_ALLOW_LEGACY_GPIO=1', '-I' + str(sdk), '-I' + str(storage),
                '-I' + str(a.reference_reader / 'Drivers/x4pro_board'), '-I' + str(a.reference_reader),
                str(ROOT / 'minimal/test/sd_async_test.c'), str(storage / 'fatfs/ff.c'),
                str(storage / 'fatfs/ffunicode.c'), '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
