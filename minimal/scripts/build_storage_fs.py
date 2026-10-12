#!/usr/bin/env python3
"""Build storage.volume with canonical shared filesystem extensions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from prepare_sdk import prepare

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
for name in ('runtime', 'drivers', 'reference-reader', 'output'):
    p.add_argument('--' + name, type=lambda x: Path(x).resolve(), required=True)
p.add_argument('--cc', default=str(Path.home() / '.platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-gcc'))
p.add_argument('--async-storage', action='store_true', help='Opt-in copied native storage worker and lazy SD discovery')
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
sdk = a.output / 'sdk'
if sdk.exists():
    shutil.rmtree(sdk)
prepare(a.runtime, a.reference_reader, sdk)
for header in (a.runtime / 'sdk/app').glob('*.h'):
    dest = sdk / header.name
    if dest.exists() and dest.read_bytes() != header.read_bytes():
        raise ValueError('Conflicting SDK header: ' + header.name)
    shutil.copyfile(header, dest)
volume = a.drivers / 'lib/StorageFatFs'
source = ROOT / 'minimal/drivers/x4pro_sd'
elf = a.output / 'driver.elf'
subprocess.run([a.cc, '-std=c11', '-O2', '-fno-ivopts', '-fPIC', '-mtext-section-literals', '-mlongcalls',
                '-fvisibility=hidden', '-fno-builtin', '-nostdlib', '-nostartfiles', '-shared',
                '-Wall', '-Wextra', '-Werror', *(['-DX4PRO_SD_ASYNC=1'] if a.async_storage else []), '-I' + str(sdk), '-I' + str(volume),
                '-I' + str(ROOT / 'Drivers/x4pro_board'), '-Wl,--hash-style=sysv',
                '-Wl,--exclude-libs,ALL', '-Wl,--no-relax', str(source / 'driver.c'),
                str(volume / 'fatfs/ff.c'), str(volume / 'fatfs/ffunicode.c'), '-lgcc', '-o', str(elf)], check=True)
sys.path.insert(0, str(a.runtime / 'scripts'))
from link_cpp_module import mapped_relocations
count = mapped_relocations(elf)
imports = sorted(line.split()[-1] for line in subprocess.check_output([a.cc.removesuffix('gcc') + 'nm', '-D', str(elf)], text=True).splitlines() if ' U ' in ' ' + line)
if set(imports) - {'strcmp', 'memcpy', 'memmove', 'memset', 'memcmp', 'strlen', 'strchr', 'strrchr', 'memchr'}:
    raise ValueError('Unexpected storage provider imports: ' + repr(imports))
manifest=json.loads((source/'manifest.json').read_text())
if a.async_storage:
    manifest['version']='0.2.23'
    manifest['requires'].append({'capability':'platform.storage-worker','api':1})
(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
receipt = {'bytes': elf.stat().st_size, 'sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
           'imports': imports, 'mapped_relocations': count, 'physical_testing': 'not performed',
           'sources': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                       for root in (volume, source, sdk) for path in sorted(root.rglob('*')) if path.is_file()}}
(a.output / 'build.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('Shared storage.volume filesystem provider built:', receipt['sha256'])
