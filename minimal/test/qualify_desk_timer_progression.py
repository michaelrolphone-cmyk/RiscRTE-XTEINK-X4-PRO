#!/usr/bin/env python3
"""Qualify injected-minute rendering with an existing selected-Home fixture.

First run System-Apps scripts/test_context_sparse_timer.py --timer-storage
against a byte-verified Home candidate. This runner reuses its unchanged normal
and ASan/UBSan binaries, schema-3 record decoder, actual Home/adapter/sleep source,
and strict terminal-sleep/provider doubles. The fixture supplies the next minute;
this test does not measure the programmed wake interval, CLEAN presentation
intent, or hardware wake reliability.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timer-proof', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    proof, output = args.timer_proof.resolve(), args.output.resolve()
    receipt = json.loads((proof / 'receipt.json').read_text())
    assert receipt['process_cases'] == 64
    assert receipt['retained_schema'] == 3 and receipt['retained_bytes'] == 408
    assert receipt['timer_live_grant_bound'] == 7
    assert '-DTEST_TIMER_STORAGE_SLEEP' in receipt['build_defines']
    assert '-DPORTABLE_ALARM_BUSY_DEFER' in receipt['build_defines']
    for source, expected in receipt['source_sha256'].items():
        assert digest(Path(source)) == expected, source
    output.mkdir(parents=True, exist_ok=True)
    runs, binaries, outputs = [], {}, {}
    for profile in ('normal', 'asan-ubsan'):
        binary = proof / profile / 'fixture'
        binaries[profile] = digest(binary)
        seed = (proof / profile / 'valid-0-0.pbm.record').read_bytes()
        assert len(seed) == 408 and seed[:6] == b'DCLK\x03\x01'
        folder = output / profile
        folder.mkdir(exist_ok=True)
        # Six traditional faces and Points; both physical orientations; cross
        # the 30-update full-refresh boundary in separate fresh processes.
        for face in range(7):
            for flip in (0, 1):
                record = bytearray(seed)
                record[6], record[9] = face, flip
                initial_minute = int.from_bytes(record[16:24], 'little')
                previous_pixels = None
                for cycle in range(1, 33):
                    prior = folder / 'prior.record'
                    prior.write_bytes(record)
                    image = folder / 'current.pbm'
                    result = subprocess.run(
                        [str(binary), 'valid', str(image)],
                        env={**os.environ, 'EXPIRY_RECORD': str(prior),
                             'EXPIRY_FLIP': str(flip), 'ASAN_OPTIONS': 'detect_leaks=0',
                             'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'},
                        capture_output=True, text=True, timeout=20)
                    assert result.returncode == 0, (profile, face, flip, cycle, result.stderr)
                    assert 'dark, no foreground policy PASS' in result.stdout
                    next_record = Path(str(image) + '.record').read_bytes()
                    assert len(next_record) == 408
                    minute = int.from_bytes(next_record[16:24], 'little')
                    assert minute == initial_minute + 60 * cycle
                    assert next_record[6] == face and next_record[9] == flip
                    assert next_record[24] == (record[24] + 1) % 30
                    pixels = image.read_bytes()
                    assert previous_pixels is None or pixels != previous_pixels
                    key = f'{face}-{flip}-{cycle}'
                    identity = {'record': hashlib.sha256(next_record).hexdigest(),
                                'pixels': hashlib.sha256(pixels).hexdigest()}
                    if profile == 'normal':
                        outputs[key] = identity
                    else:
                        assert outputs[key] == identity, key
                    runs.append({'profile': profile, 'face': face, 'flip': flip,
                                 'cycle': cycle, 'displayed_minute': minute,
                                 'refresh_modulo': next_record[24], **identity})
                    record, previous_pixels = next_record, pixels
    evidence = {'process_cases': len(runs), 'faces': 7, 'orientations': 2,
                'cycles_per_face': 32, 'minute_step_seconds': 60,
                'refresh_counter_period': 30, 'normal_sanitized_pixels_and_records': 'identical',
                'timer_proof_sha256': digest(proof / 'receipt.json'),
                'fixture_sha256': binaries, 'runs': runs, 'hardware': 'not run',
                'boundary': 'Actual delivered Home source; injected next-minute RTC, synthetic provider/sleep callbacks. Programmed sleep interval and CLEAN intent are not measured.'}
    (output / 'receipt.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(f"PASS: {len(runs)} injected-minute updates, seven faces, two orientations, "
          "32 cycles and refresh-counter rollover; normal/ASan+UBSan byte-identical")


if __name__ == '__main__':
    main()
