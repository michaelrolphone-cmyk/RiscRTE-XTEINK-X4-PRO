#!/usr/bin/env python3
"""Qualify a digest-pinned existing CI build without compiling native/packages.

Archive authority is distinct from the historical in-process producer tokens.
Original source locks and build/package receipts are preserved byte-for-byte.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import native_provision_candidate as recipe
from native_provision_payloads import inventory, package_values

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = '93ee386b7e23628f3776edc6cfd2805cf675d649'
PRODUCER_TREE = '014a47e12262db66137223c901dab337b0c2a0ad'
ORIGINAL_ROOT = Path('/__w/_temp/x4-provision-123-' + PRODUCER)
CONTRACT = ROOT / 'docs/native-provision-123/archive-input.json'
ALLOWED_FILES = {
    '.github/workflows/native-provision-123-requalify.yml',
    'docs/native-provision-123/archive-input.json', 'docs/native-provision-123/README.md',
    'scripts/native_provision_archive.py', 'scripts/native_provision_requalify.py',
    'scripts/native_provision_candidate.py', 'scripts/native_provision_qualification.py',
    'scripts/native_provision_payloads.py',
    'tests/test_native_provision_archive.py', 'tests/test_native_provision_requalify.py',
    'tests/test_native_provision_candidate.py',
}
_TOKEN = object()
require = recipe.require


def row(path):
    with path.open('rb') as source:
        return {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(source, 'sha256').hexdigest()}


def qualifier_diff(producer, qualifier):
    """Require unchanged native/package inputs and record exact reviewed deltas."""
    producer_pin = recipe.clean_source(producer, PRODUCER)
    require(producer_pin['tree'] == PRODUCER_TREE, 'Wrong original producer tree')
    revision = recipe.git(qualifier, 'rev-parse', 'HEAD').decode().strip()
    pin = recipe.clean_source(qualifier, revision)
    # The recovery checkout must retain the original producer Git object.
    require(recipe.git(qualifier, 'rev-parse', PRODUCER + '^{tree}').decode().strip() == PRODUCER_TREE,
            'Original producer Git identity unavailable')
    changed = recipe.git(qualifier, 'diff', '--name-only', PRODUCER, revision).decode().splitlines()
    require(changed and set(changed) <= ALLOWED_FILES, 'Unreviewed qualifier/native/package source change')
    rows = {}
    for name in changed:
        path = qualifier / name
        require(path.is_file() and not path.is_symlink(), 'Qualifier delta deletes/aliases a file')
        mode = recipe.git(qualifier, 'ls-tree', revision, '--', name).decode().split()[0]
        require(mode in ('100644', '100755'), 'Invalid qualifier file mode')
        previous = producer / name
        rows[name] = {'mode': mode, 'producer': row(previous) if previous.is_file() else None,
                      'qualifier': row(path)}
    return dict(source=pin, changed_files=rows)


def verify_rows(files):
    for name, expected in files.items():
        path = Path(name)
        require(path.is_file(), 'Missing original dependency: ' + name)
        require(row(path) == {key: expected[key] for key in ('bytes', 'sha256')},
                'Original dependency changed: ' + name)


class ArchivedEvidence:
    """Only create via authenticate; never substitute for a fresh build token."""
    pass


def authenticate(archive, metadata_dir, restored, sources, compiler):
    from native_provision_archive import verify_local, verify_restored
    verified = verify_restored(verify_local(CONTRACT, archive, metadata_dir), restored)
    require(verified.contract['qualification_enabled'] is True and
            verified.contract['source_revision'] == PRODUCER and
            verified.contract['source_tree'] == PRODUCER_TREE, 'Wrong or disabled qualification producer')
    require(restored.resolve() == ORIGINAL_ROOT, 'Recovery must preserve original absolute producer paths')
    proof = ArchivedEvidence()
    proof.token = _TOKEN
    proof.verified_archive = verified
    proof.archive = archive.resolve()
    proof.root = restored.resolve()
    proof.sources = dict(sources)
    proof.compiler = compiler.resolve()
    proof.inventory = verified.inventory
    proof.lock_bytes = (restored / 'build/native-build-evidence/source-lock.json').read_bytes()
    proof.lock = json.loads(proof.lock_bytes)
    proof.build_report_bytes = (restored / 'build/native-build-evidence/build-closure.json').read_bytes()
    proof.build_report = json.loads(proof.build_report_bytes)
    proof.package_receipt_bytes = (restored / 'build-packages/package-build-receipt.json').read_bytes()
    proof.package_receipt = json.loads(proof.package_receipt_bytes)
    diff = qualifier_diff(sources['product'], ROOT)
    proof.receipt = {
        'schema': 1, 'mode': 'verified-ci-archive-later-process-qualification',
        'fresh_build': False, 'same_process_qualification': False,
        'native_rebuilt': False, 'packages_rebuilt': False,
        'producer_source': proof.lock['sources']['product'],
        'archive_contract': json.loads(CONTRACT.read_bytes()),
        'archive_contract_sha256': recipe.sha(CONTRACT.read_bytes()),
        'qualifier': diff,
        'qualification_run': {
            'repository': os.environ.get('GITHUB_REPOSITORY'),
            'run_id': int(os.environ.get('GITHUB_RUN_ID', '0')),
            'attempt': int(os.environ.get('GITHUB_RUN_ATTEMPT', '0')),
            'source': os.environ.get('GITHUB_SHA'),
        },
        'original_source_lock_sha256': recipe.sha(proof.lock_bytes),
        'original_build_closure_sha256': recipe.sha(proof.build_report_bytes),
        'original_package_receipt_sha256': recipe.sha(proof.package_receipt_bytes),
        'restored_files': proof.inventory,
        'target_instructions_executed': False, 'hardware_tested': False,
    }
    require(proof.receipt['qualification_run']['repository'] == 'michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO' and
            proof.receipt['qualification_run']['source'] == diff['source']['revision'] and
            proof.receipt['qualification_run']['run_id'] > 0 and
            proof.receipt['qualification_run']['attempt'] > 0, 'Exact qualification workflow identity required')
    validate_archived_evidence(proof, sources, restored / 'build', compiler, proof.lock)
    return proof


def validate_archived_evidence(proof, sources, build, compiler, lock=None):
    require(type(proof) is ArchivedEvidence and proof.token is _TOKEN,
            'Authenticated existing CI archive required; detached receipts are not authority')
    require(proof.sources == sources and build.resolve() == proof.root / 'build' and
            compiler.resolve() == proof.compiler, 'Archived producer inputs differ')
    require((build / 'native-build-evidence/source-lock.json').read_bytes() == proof.lock_bytes and
            (build / 'native-build-evidence/build-closure.json').read_bytes() == proof.build_report_bytes and
            (proof.root / 'build-packages/package-build-receipt.json').read_bytes() == proof.package_receipt_bytes,
            'Original producer receipt bytes changed')
    require(lock is None or lock == proof.lock, 'Recovery source lock differs')
    from native_provision_archive import verify_restored
    verify_restored(proof.verified_archive, proof.root)
    recipe.verify_sources(proof.lock, sources)
    require(qualifier_diff(sources['product'], ROOT) == proof.receipt['qualifier'], 'Qualifier changed after authentication')
    for name, expected in proof.inventory.items():
        require(row(proof.root / name) == expected, 'Restored producer output changed: ' + name)
    closure = proof.build_report
    require(closure['fresh_build'] is True and closure['same_process_qualification'] is True and
            closure['sources'] == proof.lock['sources'], 'Original controlled-build closure differs')
    verify_rows(closure['files'])
    verify_rows({item['path']: item for item in closure['tools'].values()})
    for key, expected in proof.lock['native_files'].items():
        require(closure['artifacts'][key] == {name: expected[name] for name in ('bytes', 'sha256')},
                'Original native artifact binding differs: ' + key)
    recipe.checked_artifacts(proof.lock, build)
    packages = proof.package_receipt
    require(packages['same_process_build'] is True and packages == proof.lock['package_build'] and
            packages['sources'] == proof.lock['sources'], 'Original package closure differs')
    actual = inventory(proof.root / 'build-packages')
    actual.pop('package-build-receipt.json', None)
    require(actual == packages['files'], 'Archived package inventory differs')
    for item in packages['compilers'].values():
        require(row(Path(item['path']))['sha256'] == item['sha256'], 'Original package compiler changed')
    return closure, package_values(proof.root / 'build-packages')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'metadata-dir', 'restored-root', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root = args.restored_root.resolve()
    sources = {role: root / 'sources' / role for role in recipe.REQUIRED_ROLES - {'sdk'}}
    sources['sdk'] = Path(os.environ['IDF_PATH']).resolve()
    lock = json.loads((root / 'build/native-build-evidence/source-lock.json').read_bytes())
    compiler = Path(lock['compiler_family']['gcc']['path'])
    proof = authenticate(args.archive, args.metadata_dir, root, sources, compiler)
    recipe.setup_modules(sources)
    args.native_build = root / 'build'
    args.compiler = compiler
    args.lock = args.native_build / 'native-build-evidence/source-lock.json'
    args.baseline = root / 'inputs/baseline.bin'
    args.sd_archive = root / 'inputs/complete-sd.zip'
    recipe.qualify(args, sources, archived_evidence=proof)
    # Preserve the unmodified original attestations beside the recovery receipt.
    (args.output / 'original-build-closure.json').write_bytes(proof.build_report_bytes)
    (args.output / 'original-package-build-receipt.json').write_bytes(proof.package_receipt_bytes)
    (args.output / 'archive-recovery.json').write_bytes(recipe.encoded(proof.receipt))
    (args.output / 'archive-contract.json').write_bytes(CONTRACT.read_bytes())
    validate_archived_evidence(proof, sources, args.native_build, compiler, lock)
    (args.output / 'SHA256SUMS').write_text(''.join(recipe.sha(path.read_bytes()) + '  ' + path.relative_to(args.output).as_posix() + '\n'
        for path in sorted(args.output.rglob('*')) if path.is_file() and path != args.output / 'SHA256SUMS'))


if __name__ == '__main__':
    # Keep the private archive authority type identical when recipe calls back.
    sys.modules['native_provision_requalify'] = sys.modules[__name__]
    main()
