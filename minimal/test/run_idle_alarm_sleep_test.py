#!/usr/bin/env python3
"""Qualify production X4 idle/alarm restoration and reject broken restorations."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CASES = '''no-ui ui-refused ui-retained ui-unknown ui-restore-retained
prepare-unknown resume-unknown native-unsupported native-unknown ok off repeat
refused held key-retained cancel-prepared panel-refused panel-retained
panel-resume-retained touch-refused touch-retained touch-resume-retained
sd-prepare-refused sd-commit-refused sd-retained sd-unavailable wifi-retained
bt-retained acquire-retained expired api1 short tag descriptor-version
output-modes features no-resume feature-mismatch no-status no-step no-refresh
no-acknowledge no-prepare no-stop prepare-retained step-retained storage-retained
native-retained unsupported-resume release-retained due near future
resume-retained resume-rtc resume-backward ticket-stale descriptor-changed
restore-failure'''.split()
LEVEL_CASES = '''ok repeat no-ui refused native-unsupported cancel-prepared
panel-refused touch-refused sd-prepare-refused sd-commit-refused restore-failure'''.split()
MUTATION_CASES = ['ok', 'repeat', 'refused', 'cancel-prepared']
LEVELS = (0, 40, 73)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compose_sdk(args, parser, out):
    """Use source-owned app ABI and exact upstream staging, never raw driver ABI."""
    sys.path.insert(0, str(args.system / 'scripts'))
    idle = importlib.import_module('portable_idle_build')
    alarm = importlib.import_module('portable_alarm_build')
    stage = out / 'source-sdk'
    base = stage / 'base'
    base.mkdir(parents=True, exist_ok=True)
    for header in (args.system / 'lib/PortableApps/include').glob('*.h'):
        shutil.copyfile(header, base / header.name)
    # The delivered build overlays only selected canonical driver interfaces.
    # RiscBatteryGaugeV1 remains application-owned (its flags ABI differs).
    for name in ('RiscRetainedWakeV1.h', 'RiscRealtimeV1.h',
                 'RiscProviderPromotionV1.h', 'RiscRuntimeV1.h',
                 'RiscFailureEvidenceV1.h', 'RiscResidentShellV1.h'):
        shutil.copyfile(args.runtime / 'sdk/app' / name, base / name)
    profile = argparse.Namespace(
        x4_idle_source=ROOT / 'minimal/apps/portable_idle_sleep.c',
        x4_idle_sdk=args.driver_sdk, x4_idle_runtime_sdk=args.runtime / 'sdk/driver',
        paper_transitions=True, quick_actions=True, quick_radios=True,
        alarm_client=True, tagged_alarm_utilities=args.utilities,
        sparse_start=True, desk_points_face=True, contexts_rf_only=True)
    alarm.stage(profile, parser, stage, base)
    idle.configure(profile, parser, args.system, stage, base)
    return stage / 'idle-sdk/include'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('system', 'runtime', 'utilities'):
        parser.add_argument('--' + name, type=Path, required=True)
    sdk = parser.add_mutually_exclusive_group(required=True)
    sdk.add_argument('--candidate', type=Path, help='Existing composed Home directory')
    sdk.add_argument('--driver-sdk', type=Path, help='Compose test SDK from exact source owners')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/idle-policy-tests')
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    # Assertion-negative controls must not leave large core dumps.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    include = (args.candidate / 'idle-sdk/include' if args.candidate
               else compose_sdk(args, parser, out))
    local_include = out / 'include'
    local_include.mkdir(exist_ok=True)
    shutil.copyfile(args.system / 'lib/PortableApps/include/PortableAppSleep.h',
                    local_include / 'PortableAppSleep.h')
    helper = ROOT / 'minimal/apps/portable_idle_sleep.c'
    original = helper.read_text()
    restore = ' if(s.dark && !display->set_brightness(display->context,(uint16_t)portable_quick_brightness(),100))return -2;'
    if original.count(restore) != 1:
        raise AssertionError('Restoration source changed; review negative-control anchors')
    mutants = {
        'missing-restore': original.replace(restore, ' /* Test-only: restoration removed. */'),
        'constant-40': original.replace(restore, restore.replace('(uint16_t)portable_quick_brightness()', '40')),
    }
    mutation_sources = {}
    for name, source in mutants.items():
        path = out / (name + '.c')
        path.write_text(source)
        mutation_sources[name] = path
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1')
    runs, negatives, inputs, commands = [], [], {}, []
    for sanitized in (False, True):
        mode = 'sanitized' if sanitized else 'normal'
        flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                 '-DPORTABLE_ALARM_CLIENT', '-DALARM_SERVICE_TAGGED_V2',
                 '-DPORTABLE_X4_IDLE_POLICY', '-DPORTABLE_QUICK_ACTIONS']
        if sanitized:
            flags += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                      '-fno-omit-frame-pointer', '-no-pie']
        includes = [local_include, include, args.runtime / 'sdk/app',
                    args.runtime / 'sdk/driver', args.utilities / 'test/native_apps',
                    args.utilities / 'lib/Alarm/include', helper.parent]
        common = [os.environ.get('CC', 'cc'), *flags, *['-I' + str(p) for p in includes]]
        sources = [ROOT / 'minimal/test/idle_alarm_sleep_test.c',
                   args.system / 'lib/PortableApps/src/PortableTimeZone.c',
                   args.system / 'lib/PortableApps/src/PortableTimeZoneCatalog.c']
        for name, source in [('production', helper), *mutation_sources.items()]:
            exe = out / (mode + '-' + name)
            command = [*common, str(source), *map(str, sources), '-o', str(exe)]
            commands.append(command)
            subprocess.run(command, check=True)
            if name == 'production':
                # Capture exact transitive source/SDK inputs used by the compiler.
                deps = subprocess.check_output([*common, '-MM', str(source), *map(str, sources)], text=True)
                for line in deps.replace('\\\n', ' ').splitlines():
                    for token in shlex.split(line.split(': ', 1)[1]):
                        path = Path(token).resolve()
                        value = digest(path)
                        if path in inputs and inputs[path] != value:
                            raise AssertionError('Input changed during qualification: ' + str(path))
                        inputs[path] = value
                scenarios = [(case, None) for case in CASES]
                scenarios += [(case, level) for case in LEVEL_CASES for level in LEVELS]
                for case, level in scenarios:
                    command = [str(exe), case, *([] if level is None else [str(level)])]
                    result = subprocess.run(command, check=True, env=env, timeout=20,
                                            text=True, capture_output=True)
                    print(result.stdout.strip(), flush=True)
                    runs.append({'mode': mode, 'case': case, 'level': level, 'result': 'pass'})
            else:
                for case in MUTATION_CASES:
                    for level in (0, 73):
                        result = subprocess.run([str(exe), case, str(level)], env=env,
                                                timeout=20, text=True, capture_output=True)
                        # A compile failure, random crash or sanitizer failure is not a witness.
                        expected = ('h_level==h_saved_level', 'h_brightness==cycles*2')
                        if result.returncode != -signal.SIGABRT or not any(s in result.stderr for s in expected):
                            raise AssertionError((name, mode, case, level, result.returncode,
                                                  result.stdout, result.stderr))
                        negatives.append({'mode': mode, 'mutation': name, 'case': case,
                                          'level': level, 'result': 'rejected by level/count assertion',
                                          'diagnostic': result.stderr.strip()})
    for path in (Path(__file__).resolve(), args.system / 'scripts/portable_idle_build.py',
                 args.system / 'scripts/portable_alarm_build.py'):
        inputs[path] = digest(path)
    assert all(digest(path) == value for path, value in inputs.items()), 'Test input changed during matrix'
    revisions = {}
    for name, path in [('x4', ROOT), ('system', args.system), ('runtime', args.runtime),
                       ('utilities', args.utilities)]:
        revisions[name] = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    receipt = {
        'hardware_tested': False, 'runtime_and_native_hardware_mocked': True,
        'scope': 'Actual production idle helper + actual Utilities alarm service; saved-level input is a fixture.',
        'production_helper_sha256': digest(helper),
        'source_revisions': revisions,
        'source_and_sdk_sha256': {str(p): value for p, value in sorted(inputs.items())},
        'mutation_sha256': {name: digest(path) for name, path in mutation_sources.items()},
        'compiler': subprocess.check_output([os.environ.get('CC', 'cc'), '--version'], text=True).splitlines()[0],
        'commands': commands, 'runs': runs, 'negative_controls': negatives,
    }
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    assert helper.read_text() == original, 'Production source must remain unchanged'
    print(f'{len(runs)} normal/sanitizer scenarios + {len(negatives)} rejected negative controls PASS')


if __name__ == '__main__':
    main()
