#!/usr/bin/env python3
"""Assemble X4 0.1.77 from exact 0.1.76 native/panel bytes and the Daily Paper addition."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from package_reader_bin_overlay import (sha, require, encoded, inventory, write_store,
    imports, native_witness, compile_admission, NATIVE_SHA, PANEL_SHA, SCENE_SHA, RUNTIME_TREE)
from integrate_daily_digest import policy, SD_PATH

BASE_SHA = '5a00e718132b8381f0e58a8af1f1b40301580ba9d73f164c20561fae98b962c5'
READER_SHA = '90a77b26635ebac97e57b87ab9e1cc551addb7f672d45b22e350130d91aa82d9'
IMAGE_NAME = 'X4-0.1.77-Daily-Paper-Panel-0.1.12-full-0x0.bin'
CHANGED = {'boot.json', 'cohort.json', 'default.elf', 'default.json', 'springboard.elf',
           'springboard.json', 'ebook_reader.json', 'daily_digest.json',
           'net-http-client/driver.elf', 'net-http-client/manifest.json'}


def prepare(a):
    require(not a.output.exists(), 'Choose a new output directory')
    require(re.fullmatch('[0-9a-f]{40}', a.source_revision), 'Invalid source commit')
    tree = subprocess.check_output(['git', '-C', str(a.runtime), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    require(tree == RUNTIME_TREE, 'Use the deployed Runtime 0.2.5 source tree')
    require(not subprocess.check_output(['git', '-C', str(a.runtime), 'status', '--porcelain', '--untracked-files=no'], text=True), 'Runtime admission source changed')
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from paired_bank_images import parse_record
    raw = a.baseline.read_bytes()
    require(len(raw) == 0x1000000 and sha(raw) == BASE_SHA, 'Use the exact completed 0.1.76 full BIN')
    pair = parse_record(raw[0xff2000:0xff2060], True)
    require(pair[2] == 0, 'Expected baseline active bank zero')
    firmware = raw[0x10000:0x10000+pair[3]]
    require(sha(firmware) == NATIVE_SHA and pair[6] == hashlib.sha256(firmware).digest(), 'Native baseline mismatch')
    require(raw[0x10000+len(firmware):0x270000] == b'\xff'*(0x260000-len(firmware)), 'Native padding changed')
    require(b'RISC_APP_POLICY_ROWS:24\0' in firmware and b'RISC_APP_REQUIREMENT_ROWS:24\0' in firmware, 'Native policy bounds differ')
    fs = raw[0x2f0000:0x800000]
    require(pair[7] == hashlib.sha256(fs).digest(), 'Baseline paired metadata differs')
    old = read_image(fs, 0x510000)
    require(len(old) == 92 and pack(old)[0] == fs, 'Baseline filesystem not reproduced byte-for-byte')
    require(sha(old['panel/driver.elf']) == PANEL_SHA and sha(old['ui-scene/driver.elf']) == SCENE_SHA, 'Panel/scene baseline differs')
    new = dict(old)
    for app, version in (('default', '0.4.8'), ('springboard', '1.7.31')):
        for ext in ('elf', 'json'):
            new[app+'.'+ext] = (a.launchers/app/(app+'.'+ext)).read_bytes()
        before, after = json.loads(old[app+'.json']), json.loads(new[app+'.json'])
        require(after['version'] == version, 'Wrong launcher version')
        before.pop('version'); after.pop('version')
        require(before == after, 'Existing launcher capability requirements changed')
    reader = a.reader.read_bytes()
    require(sha(reader) == READER_SHA, 'Use the completed Reader 0.1.7 page-turn fix')
    new['ebook_reader.json'] = a.reader_manifest.read_bytes()
    before, after = json.loads(old['ebook_reader.json']), json.loads(new['ebook_reader.json'])
    require(after['version'] == '0.1.7', 'Wrong Reader version')
    before.pop('version'); after.pop('version')
    require(before == after, 'Reader admission policy changed')
    daily = (a.daily_package/SD_PATH).read_bytes()
    new['daily_digest.json'] = (a.daily_package/'firmware-integration/daily_digest.json').read_bytes()
    manifest = json.loads(new['daily_digest.json'])
    require(manifest['version'] == '0.1.0', 'Wrong Daily Paper version')
    new['boot.json'] = encoded(policy(json.loads(old['boot.json']), manifest))
    for name in ('driver.elf', 'manifest.json'):
        new['net-http-client/'+name] = (a.daily_package/'firmware-integration/net-http-client'/name).read_bytes()
    cohort = json.loads(old['cohort.json'])
    require(cohort['version'] == '0.1.76' and cohort['firmware_sha256'] == NATIVE_SHA, 'Wrong starting cohort')
    cohort.update(version='0.1.77', source_revision=a.source_revision)
    new['cohort.json'] = encoded(cohort)
    changed = {n for n in new if new[n] != old.get(n)}
    require(changed == CHANGED and old.keys() <= new.keys(), 'Unexpected changes to existing modules')
    boot = json.loads(new['boot.json'])
    require(len(boot['app_capabilities']) == 26 and len(boot['drivers']) == 28, 'Incomplete app/provider inventory')
    require(boot['resident_shell']['foreground'].count('daily_digest.elf') == 1, 'Wrong foreground registration')
    catalog = json.loads((a.launchers/'launcher-build.json').read_text())['catalog']
    require({r['file_name'] for r in catalog} == {json.loads(new[row['manifest']])['file_name'] for row in boot['app_capabilities']} - {'default.elf', 'springboard.elf'}, 'Launcher/boot app inventory mismatch')
    a.output.mkdir(parents=True)
    write_store(a.output/'baseline-store', old)
    write_store(a.output/'store', new)
    write_store(a.output/'sd', {SD_PATH: daily, 'Apps/daily-digest/manifest.json': new['daily_digest.json'],
                 'Apps/ebook-reader/ebook_reader.elf': reader, 'Apps/ebook-reader/manifest.json': new['ebook_reader.json']})
    (a.output/'native.bin').write_bytes(firmware)
    exported, witness = native_witness(a.runtime, firmware)
    (a.output/'native-exports.json').write_bytes(encoded(witness))
    (a.output/'exports.json').write_bytes(encoded(sorted(exported)))
    (a.output/'preparation.json').write_bytes(encoded({'runtime_tree': tree, 'source_revision': a.source_revision,
        'before': inventory(old), 'after': inventory(new), 'app_count':26, 'provider_count':28}))
    print('Prepared 26 apps / 28 providers with native and panel bytes unchanged.', flush=True)


def validate(a, sanitized):
    directory = a.output/('sanitized' if sanitized else 'plain')
    exported = json.loads((a.output/'exports.json').read_text())
    info = compile_admission(a.runtime, a.tools, directory, exported, sanitized)
    store = a.output/'store'
    modules = [(p, p.as_posix().endswith('/driver.elf')) for p in sorted(store.rglob('*.elf'))]
    require(len(modules) == 38, 'Incomplete internal module set')
    modules += [(a.output/'sd'/SD_PATH, False), (a.output/'sd/Apps/ebook-reader/ebook_reader.elf', False)]
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    negative = 0
    for path, provider in modules:
        names = imports(path.read_bytes())
        require(set(names) <= set(exported), 'Unresolved native import: '+str(path))
        command = [str(directory/'strict'), 'driver' if provider else 'app', str(path)]
        subprocess.run(command, check=True, env=env, timeout=30)
        if path.name in ('default.elf', 'springboard.elf', 'ebook_reader.elf', 'daily_digest.elf') or path.parent.name == 'net-http-client':
            # Exhaustive missing-import rejection runs once in the normal pass.
            # The sanitizer pass repeats a representative miss per changed module.
            for symbol in names[:1] if sanitized else names:
                subprocess.run(command+[symbol], check=True, env=env, timeout=30)
                negative += 1
    outcomes = []
    # Full-flash admission is fresh installation followed by exact self-validation.
    # OTA expansion into an already-used Wi-Fi namespace is intentionally refused
    # by the deployed Runtime. Exercise that separately, not as a passing update.
    for active, candidate, count in (('baseline-store', 'baseline-store', 37), ('store', 'store', 38)):
        result = subprocess.run([str(directory/'cohort'), str(a.output/active), str(a.output/candidate)],
            check=True, capture_output=True, text=True, env=env, timeout=45)
        (directory/(active+'.log')).write_text(result.stdout+result.stderr)
        row = json.loads(result.stdout)
        require(row['prepared'] and row['cohort_validated'] and row['elf_count'] == count and
                row['hardware_calls'] == row['storage_calls'] == 0, 'Cohort validation failed: '+str(row))
        outcomes.append(dict(row, active=active, candidate=candidate))
    result = subprocess.run([str(directory/'cohort'), str(a.output/'baseline-store'), str(store)],
        check=True, capture_output=True, text=True, env=env, timeout=45)
    transition = json.loads(result.stdout)
    require(transition['prepared'] and not transition['cohort_validated'] and
            transition['hardware_calls'] == transition['storage_calls'] == 0,
            'Unexpected existing-namespace OTA policy result')
    (directory/'ota-transition.log').write_text(result.stdout+result.stderr)
    info.update(strict_modules=len(modules), missing_import_rejections=negative,
                wrong_role_rejections=len(modules), unsafe_operation_rejections=len(modules),
                cohorts=outcomes, ota_transition_accepted=False, ota_transition=transition,
                installation='full-flash; not an in-place OTA package')
    (directory/'validation.json').write_bytes(encoded(info))
    print(('ASan/UBSan' if sanitized else 'Normal')+': 40 modules and both installed cohorts pass; OTA expansion correctly refused.', flush=True)


def finish(a):
    from current_bootfs import build as pack
    from read_only_spiffs import read_image
    from paired_bank_images import initial_bank_state, parse_record
    from native_binary_exports import segments
    raw = a.baseline.read_bytes()
    require(sha(raw) == BASE_SHA, 'Baseline changed during assembly')
    prepared = json.loads((a.output/'preparation.json').read_text())
    old = {p.relative_to(a.output/'baseline-store').as_posix(): p.read_bytes() for p in (a.output/'baseline-store').rglob('*') if p.is_file()}
    new = {p.relative_to(a.output/'store').as_posix(): p.read_bytes() for p in (a.output/'store').rglob('*') if p.is_file()}
    require(inventory(new) == prepared['after'] and inventory(old) == prepared['before'], 'Admission mutated the staged store')
    checks = [json.loads((a.output/name/'validation.json').read_text()) for name in ('plain','sanitized')]
    updated, capacity = pack(new)
    require(pack(new)[0] == updated, 'Nondeterministic output store')
    for label, data, expected in (('baseline', raw[0x2f0000:0x800000], old), ('output', updated, new)):
        image = a.output/(label+'-bootfs.bin'); image.write_bytes(data)
        dest = a.output/(label+'-independent'); dest.mkdir()
        subprocess.run([str(a.mkspiffs), '-u', str(dest), '-p', '256', '-b', '4096', '-s', str(0x510000), str(image)],
                       check=True, stdout=subprocess.DEVNULL, timeout=60)
        require({p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()} == expected, 'Independent SPIFFS readback differs')
    firmware = (a.output/'native.bin').read_bytes()
    require(sha(firmware) == NATIVE_SHA, 'Native bytes changed')
    segments(firmware)
    bank = initial_bank_state(firmware, updated, True)
    require(initial_bank_state(firmware, raw[0x2f0000:0x800000], True) == raw[0xff2000:0xff4000], 'Unexpected baseline bank state')
    pair = parse_record(bank[:96], True)
    require(pair[6] == hashlib.sha256(firmware).digest() and pair[7] == hashlib.sha256(updated).digest(), 'New paired hashes/CRC differ')
    image = bytearray(raw)
    image[0x2f0000:0x800000] = updated; image[0xff2000:0xff4000] = bank
    ranges = [(0,0x2f0000), (0x800000,0xff2000), (0xff4000,len(raw))]
    require(all(image[lo:hi] == raw[lo:hi] for lo,hi in ranges), 'Unexpected write outside boot store and bank record')
    require(read_image(bytes(image[0x2f0000:0x800000]),0x510000) == new, 'Final BIN readback mismatch')
    (a.output/IMAGE_NAME).write_bytes(image)
    (a.output/'bank-state.bin').write_bytes(bank)
    report = {'schema':'x4.daily-paper-firmware.v1','version':'0.1.77',
        'image':{'name':IMAGE_NAME,'bytes':len(image),'flash_offset':0,'sha256':sha(image)},
        'baseline_sha256':BASE_SHA,'source_revision':prepared['source_revision'],
        'native_firmware_sha256':NATIVE_SHA,'native_unchanged':True,'runtime_version':'0.2.5',
        'runtime_tree':prepared['runtime_tree'],'changed_internal_files':sorted(CHANGED),
        'unchanged_internal_files':len(new)-len(CHANGED),'app_count':26,'provider_count':28,
        'panel_version':'0.1.12','panel_sha256':PANEL_SHA,'panel_unchanged':True,
        'scene_version':'0.3.5','scene_sha256':SCENE_SHA,'scene_unchanged':True,
        'reader':{'version':'0.1.7','sha256':READER_SHA,'sd_path':'Apps/ebook-reader/ebook_reader.elf'},
        'daily_paper':{'version':'0.1.0','sha256':sha((a.output/'sd'/SD_PATH).read_bytes()),'sd_path':SD_PATH},
        'launchers':json.loads((a.launchers/'launcher-build.json').read_text()),
        'all_file_inventories':{'before':inventory(old),'after':inventory(new)},
        'unchanged_ranges':[{'offset':lo,'bytes':hi-lo,'sha256':sha(raw[lo:hi])} for lo,hi in ranges],
        'store_generator':capacity,'independent_mkspiffs_sha256':sha(a.mkspiffs.read_bytes()),
        'independent_baseline_and_output_readbacks':True,'paired_sha_crc_verified':True,
        'validation':checks,'hardware_tested':False,'target_instructions_executed':False,
        'full_flash_overwrites_internal_data':True, 'ota_transition_accepted':False}
    (a.output/'build-custody.json').write_bytes(encoded(report))
    print(json.dumps(report['image']), flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','runtime','tools','launchers','daily-package','reader','reader-manifest','mkspiffs','output'):
        p.add_argument('--'+n,type=lambda s:Path(s).resolve(),required=True)
    p.add_argument('--source-revision',required=True)
    p.add_argument('--phase', choices=['all','prepare','plain','sanitized','finish'], default='all')
    a = p.parse_args()
    sys.path[:0] = [str(a.tools/'scripts'),str(a.runtime/'scripts')]
    if a.phase in ('all','prepare'): prepare(a)
    if a.phase in ('all','plain'): validate(a,False)
    if a.phase in ('all','sanitized'): validate(a,True)
    if a.phase in ('all','finish'): finish(a)
