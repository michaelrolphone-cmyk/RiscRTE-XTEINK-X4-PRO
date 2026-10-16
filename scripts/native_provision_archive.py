#!/usr/bin/env python3
"""Recover one reviewed CI archive without rebuilding or changing its bytes.

The archive digest and exact failed producer attempt are the trust anchor. A
saved extraction receipt is never authority: load_verified hashes the original
ZIP and every restored member again. Source clones and new qualification output
are separate from the archived build/package bytes.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/native-provision-123/archive-input.json'
REPOSITORY = 'michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO'
WORKFLOW = '.github/workflows/native-provision-123.yml'
MAX_ARCHIVE = 2 * 1024**3 - 1
MAX_EXPANSION = 8 * 1024**3
MAX_MEMBER = 1024**3
MAX_MEMBERS = 50000
MAX_SMALL = 64 * 1024**2
MAX_QUALIFICATION = 256 * 1024**2
MAX_DEBUG = 64 * 1024**2
MAX_DEBUG_FILES = 1000
CHUNK = 1024**2
SMALL_FILES = frozenset({
    'build-packages/home-build/home/default.elf',
    'build-packages/home-build/home/default.json',
    'build-packages/service/driver.elf',
    'build-packages/service/manifest.json',
    'build-packages/service/build.json',
    'build-packages/package-build-receipt.json',
    'build/riscrte_native.bin', 'build/riscrte_native.elf', 'build/riscrte_native.map',
    'build/native-build-evidence/source-lock.json',
    'build/native-build-evidence/build-closure.json',
})
EXPECTED_STEPS = {
    'Clone exact independent clean source roots': 'success',
    'Download and audit the immutable .122 factory and matching complete SD': 'success',
    'Product host and current Home integration gates': 'success',
    'Generic serial protocol storage and custody host gates': 'success',
    'Fresh .123 packages and native build with complete qualification': 'failure',
    'Native artifact and workspace checks': 'skipped',
    'Preserve exact source SDK baseline package and build evidence': 'success',
    'Upload bounded qualification and startup receipts': 'success',
    'Upload candidate delivery assets': 'success',
    'Upload complete reproducibility evidence': 'success',
}
_TOKEN = object()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hex_value(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def safe_path(name):
    require(isinstance(name, str) and name and len(name) <= 1024 and
            all(32 < ord(c) < 127 for c in name) and '\\' not in name and ':' not in name,
            'Unsafe archive member')
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and str(path) == name and
            not any(part in ('.', '..') for part in path.parts), 'Unsafe archive path')
    return path


def no_symlink(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink in custody path')
    return path


def file_record(path, limit=MAX_ARCHIVE):
    path = no_symlink(path)
    require(path.is_file() and 0 < path.stat().st_size <= limit, 'Missing/oversized custody file')
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            size += len(block)
            require(size <= limit, 'Custody file grew beyond bound')
            digest.update(block)
    return {'bytes': size, 'sha256': digest.hexdigest()}


def contract(path=CONTRACT):
    value = json.loads(Path(path).read_bytes())
    require(value['schema'] == 1 and value['repository'] == REPOSITORY and
            type(value['qualification_enabled']) is bool and
            hex_value(value['source_revision'], 40) and hex_value(value['source_tree'], 40),
            'Invalid archive contract')
    require(value['original_root'] == '/__w/_temp/x4-provision-123-' + value['source_revision'],
            'Unexpected original producer root')
    run, artifact = value['run'], value['artifact']
    require(all(type(run[k]) is int and run[k] > 0 for k in ('id', 'attempt', 'job_id', 'workflow_id', 'repository_id', 'pull_request')) and
            run['event'] == 'pull_request' and run['conclusion'] == 'failure' and
            run['workflow'] == WORKFLOW and hex_value(run['workflow_sha256']), 'Invalid producer attempt pin')
    require(type(artifact['id']) is int and artifact['id'] > 0 and
            type(artifact['bytes']) is int and 0 < artifact['bytes'] <= MAX_ARCHIVE and
            hex_value(artifact['sha256']) and artifact['name'] ==
            'x4-native-provision-123-reproducibility-' + value['source_revision'], 'Invalid archive pin')
    return value


def verify_metadata(c, metadata):
    run, jobs, artifacts, commit = (metadata[n] for n in ('run', 'jobs', 'artifacts', 'commit'))
    pin = c['run']
    require(run['id'] == pin['id'] and run['run_attempt'] == pin['attempt'] and
            run['workflow_id'] == pin['workflow_id'] and run['path'] == WORKFLOW and
            run['head_sha'] == c['source_revision'] and run['head_branch'] == pin['head_branch'] and
            run['event'] == pin['event'] and run['status'] == 'completed' and
            run['conclusion'] == 'failure', 'Wrong original producer run/attempt')
    require(run['repository']['id'] == run['head_repository']['id'] == pin['repository_id'] and
            run['repository']['full_name'] == run['head_repository']['full_name'] == REPOSITORY,
            'Wrong producer repository')
    prs = run['pull_requests']
    require(len(prs) == 1 and prs[0]['number'] == pin['pull_request'] and
            prs[0]['head']['ref'] == pin['head_branch'] and hex_value(prs[0]['head']['sha'], 40) and
            prs[0]['head']['repo']['id'] == prs[0]['base']['repo']['id'] == pin['repository_id'],
            'Wrong producer PR identity')
    # The PR's live head may advance. Only run/job/artifact SHAs identify history.
    require(commit['sha'] == c['source_revision'] and commit['commit']['tree']['sha'] == c['source_tree'] and
            sha(metadata['workflow']) == pin['workflow_sha256'], 'Wrong producer source/workflow bytes')
    require(jobs['total_count'] == len(jobs['jobs']) == 1, 'Incomplete/ambiguous producer jobs')
    job = jobs['jobs'][0]
    require(job['id'] == pin['job_id'] and job['run_id'] == pin['id'] and
            job['run_attempt'] == pin['attempt'] and job['head_sha'] == c['source_revision'] and
            job['name'] == 'qualify' and job['status'] == 'completed' and job['conclusion'] == 'failure',
            'Wrong producer job')
    for name, conclusion in EXPECTED_STEPS.items():
        found = [s for s in job['steps'] if s['name'] == name]
        require(len(found) == 1 and found[0]['status'] == 'completed' and found[0]['conclusion'] == conclusion,
                'Unexpected original producer step: ' + name)
    require(artifacts['total_count'] == len(artifacts['artifacts']) == 2 and
            len({a['id'] for a in artifacts['artifacts']}) == 2, 'Incomplete/ambiguous original artifact set')
    found = [a for a in artifacts['artifacts'] if a['id'] == c['artifact']['id']]
    require(len(found) == 1, 'Original archive is missing')
    artifact, expected = found[0], c['artifact']
    require(artifact['name'] == expected['name'] and artifact['size_in_bytes'] == expected['bytes'] and
            artifact['digest'] == 'sha256:' + expected['sha256'] and artifact['expired'] is False,
            'Original archive identity differs')
    origin = artifact['workflow_run']
    require(origin['id'] == pin['id'] and origin['head_sha'] == c['source_revision'] and
            origin['head_branch'] == pin['head_branch'] and
            origin['repository_id'] == origin['head_repository_id'] == pin['repository_id'],
            'Archive does not belong to original producer')
    dates = [datetime.fromisoformat(v.replace('Z', '+00:00')) for v in
             (job['started_at'], artifact['created_at'], job['completed_at'])]
    require(all(d.tzinfo is not None for d in dates) and dates[0] <= dates[1] <= dates[2],
            'Archive is outside exact producer attempt')


class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password,
                'Unsafe API redirect')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        redirected.remove_header('Authorization')
        return redirected


class Github:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), HttpsRedirect())

    def response(self, endpoint):
        require(endpoint.startswith('repos/' + REPOSITORY + '/') and not any(c in endpoint for c in ('\r', '\n', '#')),
                'Unapproved API endpoint')
        headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
        if os.environ.get('GH_TOKEN'):
            headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
        request = urllib.request.Request('https://api.github.com/' + endpoint, headers=headers)
        return self.opener.open(request, timeout=60)

    def json(self, endpoint):
        with self.response(endpoint) as response:
            require(response.status == 200, 'API request did not succeed')
            raw = response.read(8 * CHUNK + 1)
            require(len(raw) <= 8 * CHUNK, 'API response exceeds bound')
            return json.loads(raw)

    def download(self, endpoint, target, expected):
        start, size, digest = time.monotonic(), 0, hashlib.sha256()
        with self.response(endpoint) as response, target.open('xb') as output:
            require(response.status == 200, 'Archive download did not succeed')
            for block in iter(lambda: response.read(CHUNK), b''):
                size += len(block)
                require(size <= expected['bytes'] and time.monotonic() - start <= 900, 'Archive download exceeds bound')
                digest.update(block); output.write(block)
        require({'bytes': size, 'sha256': digest.hexdigest()} ==
                {k: expected[k] for k in ('bytes', 'sha256')}, 'Downloaded archive digest/size differs')


def fetch(c, output, api=None):
    output = no_symlink(output)
    require(not output.exists(), 'Evidence output must be new')
    api = api or Github()
    prefix = 'repos/' + REPOSITORY
    attempt = prefix + '/actions/runs/%d/attempts/%d' % (c['run']['id'], c['run']['attempt'])
    metadata = {
        'run': api.json(attempt), 'jobs': api.json(attempt + '/jobs?per_page=100'),
        'artifacts': api.json(prefix + '/actions/runs/%d/artifacts?per_page=100' % c['run']['id']),
        'commit': api.json(prefix + '/commits/' + c['source_revision']),
    }
    import base64
    workflow = api.json(prefix + '/contents/' + WORKFLOW + '?ref=' + c['source_revision'])
    require(workflow['type'] == 'file' and workflow['path'] == WORKFLOW and workflow['encoding'] == 'base64',
            'Exact producer workflow is unavailable')
    metadata['workflow'] = base64.b64decode(workflow['content'])
    verify_metadata(c, metadata)
    output.mkdir(parents=True)
    for name, value in metadata.items():
        (output / (name + ('.yml' if name == 'workflow' else '.json'))).write_bytes(
            value if name == 'workflow' else encoded(value))
    archive = output / 'reproducibility-evidence.zip'
    api.download(prefix + '/actions/artifacts/%d/zip' % c['artifact']['id'], archive, c['artifact'])
    verify_archive(c, archive)
    return archive


def read_metadata(directory):
    directory = no_symlink(directory)
    result = {}
    for name in ('run', 'jobs', 'artifacts', 'commit', 'workflow'):
        path = no_symlink(directory / (name + ('.yml' if name == 'workflow' else '.json')))
        require(path.is_file() and path.stat().st_size <= 8 * CHUNK, 'Metadata missing/oversized')
        result[name] = path.read_bytes() if name == 'workflow' else json.loads(path.read_bytes())
    return result


def verify_archive(c, path):
    require(file_record(path) == {k: c['artifact'][k] for k in ('bytes', 'sha256')},
            'Original ZIP digest/size differs')


@dataclass(frozen=True)
class VerifiedArchive:
    token: object
    contract: dict
    archive: Path
    metadata: dict
    receipt: dict
    selected_file_inventory: dict

    @property
    def archive_path(self):
        return self.archive

    @property
    def inventory(self):
        return self.selected_file_inventory


def verify_local(contract_path, archive_path, metadata_dir):
    c = contract(contract_path)
    metadata = read_metadata(metadata_dir)
    verify_metadata(c, metadata)
    archive = no_symlink(archive_path)
    verify_archive(c, archive)
    receipt = {'schema': 1, 'compiled_product_revision': c['source_revision'],
               'compiled_product_tree': c['source_tree'], 'producer_run': c['run'],
               'original_archive': c['artifact'], 'original_archive_repacked': False,
               'native_rebuilt': False, 'packages_rebuilt': False, 'fresh_build': False,
               'hardware_tested': False}
    return VerifiedArchive(_TOKEN, c, archive, metadata, receipt, {})


def zip_members(archive):
    rows = archive.infolist()
    require(0 < len(rows) <= MAX_MEMBERS, 'Archive member-count bound exceeded')
    names, files, total = set(), {}, 0
    for row in rows:
        require(row.orig_filename == row.filename, 'NUL/rewritten ZIP member name')
        name = row.filename[:-1] if row.is_dir() else row.filename
        safe_path(name)
        require(name not in names, 'Duplicate ZIP member')
        names.add(name)
        mode = stat.S_IFMT(row.external_attr >> 16)
        require(mode in (0, stat.S_IFREG, stat.S_IFDIR) and not row.flag_bits & 1,
                'Special/encrypted ZIP member')
        require(row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'Unsupported ZIP compression')
        if row.is_dir():
            require(row.file_size == 0 and mode != stat.S_IFREG, 'Invalid ZIP directory')
            continue
        require(mode != stat.S_IFDIR and 0 <= row.file_size <= MAX_MEMBER, 'Oversized/invalid ZIP member')
        total += row.file_size
        require(total <= MAX_EXPANSION, 'ZIP expansion exceeds bound')
        files[name] = row
    require(files and not any(any(str(parent) in files for parent in PurePosixPath(name).parents
                                 if str(parent) != '.') for name in names), 'ZIP file/directory collision')
    return files


def member_record(archive, row, output=None):
    digest, size = hashlib.sha256(), 0
    with archive.open(row) as source:
        for block in iter(lambda: source.read(CHUNK), b''):
            size += len(block)
            require(size <= row.file_size, 'Expanded ZIP member exceeds declared size')
            digest.update(block)
            if output is not None:
                output.write(block)
    require(size == row.file_size, 'Incomplete ZIP member')
    return {'bytes': size, 'sha256': digest.hexdigest()}


def extract_verified(proof, destination, selected=None):
    require(type(proof) is VerifiedArchive and proof.token is _TOKEN, 'Verified archive required')
    destination = no_symlink(destination)
    require(not destination.exists(), 'Restoration output must be new')
    verify_archive(proof.contract, proof.archive)
    inventory = {}
    with zipfile.ZipFile(proof.archive) as archive:
        files = zip_members(archive)
        chosen = set(files) if selected is None else set(selected)
        require(chosen and chosen <= set(files), 'Selected archive inputs are missing')
        if selected is not None:
            require(sum(files[n].file_size for n in chosen) <= MAX_SMALL, 'Small bundle exceeds bound')
        destination.mkdir(parents=True)
        for name in sorted(chosen):
            path = no_symlink(destination / name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as out:
                inventory[name] = member_record(archive, files[name], out)
            require(file_record_allow_empty(path) == inventory[name], 'Restored member differs')
    verify_archive(proof.contract, proof.archive)
    return inventory


def file_record_allow_empty(path):
    path = no_symlink(path)
    require(path.is_file(), 'Restored file is missing')
    if path.stat().st_size == 0:
        return {'bytes': 0, 'sha256': sha(b'')}
    return file_record(path, MAX_MEMBER)


def verify_restored(proof, restored_root):
    require(type(proof) is VerifiedArchive and proof.token is _TOKEN, 'Verified archive required')
    restored_root = no_symlink(restored_root)
    require(str(restored_root) == proof.contract['original_root'] and restored_root.is_dir(),
            'Restore the exact original producer root')
    inventory = {}
    with zipfile.ZipFile(proof.archive) as source:
        files = zip_members(source)
        for name, row in files.items():
            expected = member_record(source, row)
            require(file_record_allow_empty(restored_root / name) == expected, 'Restored archive member differs: ' + name)
            inventory[name] = expected
    actual = set()
    for path in restored_root.rglob('*'):
        relative = path.relative_to(restored_root)
        # Exact Git source clones are separately checked by the qualifier.
        if relative.parts[0] == 'sources':
            continue
        require(not path.is_symlink(), 'Symlink in restored archive tree')
        if path.is_file():
            actual.add(relative.as_posix())
    require(actual == set(inventory), 'Restored archive file set changed')
    verify_archive(proof.contract, proof.archive)
    return VerifiedArchive(_TOKEN, proof.contract, proof.archive, proof.metadata, proof.receipt, inventory)


def load_verified(archive, metadata_dir, restored_root, contract_path=CONTRACT):
    return verify_restored(verify_local(contract_path, archive, metadata_dir), restored_root)


def qualification_original_names(inventory):
    required = {
        'build/native-build-evidence/source-lock.json', 'build/compile_commands.json',
        'build/riscrte_native.elf', 'build/riscrte_native.map',
        'build/config/sdkconfig.h', 'build/config/sdkconfig.json',
        'build/platform-capacity-probe/probe.cpp', 'build/platform-capacity-probe/receipt.json',
        'build/platform-capacity-probe/capacity-32.o', 'build/platform-capacity-probe/capacity-40.o',
        'build-packages/package-build-receipt.json',
        'metadata/workflow.yml', 'metadata/source-rows.txt', 'metadata/sdk-tools.json',
        'metadata/input-urls.json', 'source-evidence/sdk-submodules.txt', 'source-evidence/SHA256SUMS',
        'serial-product/normal.json', 'serial-product/sanitized.json',
        'platform-capacity/normal.json', 'platform-capacity/sanitized.json',
    }
    for role in ('product', 'runtime', 'system', 'drivers', 'sdk', 'image_helper', 'reader', 'utilities'):
        required.update('source-evidence/' + role + '-' + suffix + '.txt' for suffix in ('identity', 'status'))
    require(required <= set(inventory), 'Required original bounded evidence is missing')
    return required | {name for name in inventory if name.startswith(('build/toolchain/', 'logs/')) or
                       name.startswith('build/qualification/') and name.endswith('.json')}


def stage_qualification(proof, restored_root, candidate, qualifier_metadata, recovery_logs, metadata_dir, output):
    """Build one bounded evidence root without common-ancestor path expansion."""
    proof = verify_restored(proof, restored_root)
    output = no_symlink(output)
    roots = [no_symlink(p) for p in (restored_root, candidate, qualifier_metadata, recovery_logs, metadata_dir)]
    require(not output.exists() and all(not output.is_relative_to(p) and not p.is_relative_to(output) for p in roots),
            'Bounded evidence output must be new and disjoint')
    rows = {name: (Path(restored_root) / name, proof.inventory[name])
            for name in qualification_original_names(proof.inventory)}
    candidate_names = {'qualification.json', 'source-lock.json', 'SHA256SUMS',
                       'serial-product-normal.json', 'serial-product-sanitized.json',
                       'archive-recovery.json', 'archive-contract.json',
                       'original-build-closure.json', 'original-package-build-receipt.json'}
    require(all((Path(candidate) / name).is_file() for name in candidate_names), 'Recovery receipts are incomplete')
    candidate_names.update(p.relative_to(candidate).as_posix() for p in (Path(candidate) / 'feed').glob('*.json'))
    for name in sorted(candidate_names):
        path = no_symlink(Path(candidate) / name)
        rows['candidate/' + name] = (path, file_record_allow_empty(path))
    require((Path(qualifier_metadata) / 'workflow.yml').is_file() and
            (Path(qualifier_metadata) / 'qualifier-identity.txt').is_file() and
            (Path(qualifier_metadata) / 'qualifier-status.txt').is_file() and
            (Path(qualifier_metadata) / 'qualifier-source.tar.gz').is_file(), 'Separate qualifier identity/source missing')
    for prefix, source in (('qualifier-metadata', qualifier_metadata), ('recovery-logs', recovery_logs),
                           ('recovery-api', metadata_dir)):
        for path in sorted(Path(source).iterdir()):
            # Keep the original 782 MB ZIP separate and verbatim. The publisher
            # retrieves it by its original producer artifact ID and digest.
            if prefix == 'recovery-api' and path.name == 'reproducibility-evidence.zip':
                continue
            require(path.is_file() and not path.is_symlink(), 'Unexpected evidence member')
            name = prefix + '/' + path.name; safe_path(name)
            rows[name] = (path, file_record_allow_empty(path))
    staged = {name: expected for name, (_, expected) in sorted(rows.items())}
    receipt = {'schema': 1, 'original_archive': proof.contract['artifact'],
               'source_revision': proof.contract['source_revision'], 'files': staged,
               'original_archive_repacked': False, 'native_rebuilt': False, 'packages_rebuilt': False}
    receipt_bytes = encoded(receipt)
    require(len(rows) < 5000 and sum(record['bytes'] for _, record in rows.values()) + len(receipt_bytes) <= MAX_QUALIFICATION,
            'Bounded qualification evidence exceeds limit')
    output.mkdir(parents=True)
    for name, (source, expected) in sorted(rows.items()):
        safe_path(name)
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with source.open('rb') as src, target.open('xb') as dst:
            for block in iter(lambda: src.read(CHUNK), b''):
                count += len(block)
                require(count <= expected['bytes'], 'Evidence grew during staging: ' + name)
                dst.write(block)
        require(file_record_allow_empty(target) == file_record_allow_empty(source) == expected,
                'Evidence changed during staging: ' + name)
    require((output / 'metadata/workflow.yml').read_bytes() == proof.metadata['workflow'],
            'Original workflow identity was replaced by qualifier workflow')
    (output / 'qualification-evidence.json').write_bytes(receipt_bytes)
    return receipt


def stage_debug(qualifier_metadata, recovery_logs, metadata_dir, output):
    """Preserve bounded failure diagnostics, without granting qualification authority."""
    output = no_symlink(output)
    roots = [no_symlink(p) for p in (qualifier_metadata, recovery_logs, metadata_dir)]
    require(not output.exists() and all(not output.is_relative_to(p) and not p.is_relative_to(output) for p in roots),
            'Diagnostic output must be new and disjoint')
    rows = {}
    for prefix, source in zip(('qualifier-metadata', 'recovery-logs', 'recovery-api'), roots):
        if not source.exists():
            continue
        require(source.is_dir(), 'Diagnostic input is not a directory')
        for path in sorted(source.iterdir()):
            if prefix == 'recovery-api' and path.name == 'reproducibility-evidence.zip':
                continue
            allowed = (path.suffix == '.log' if prefix == 'recovery-logs' else
                       path.name in {'workflow.yml', 'qualifier-identity.txt', 'qualifier-status.txt',
                                     'qualifier-source.tar.gz'} if prefix == 'qualifier-metadata' else
                       path.suffix == '.json' or path.name == 'workflow.yml')
            require(allowed and path.is_file() and not path.is_symlink(), 'Unexpected diagnostic member')
            name = prefix + '/' + path.name; safe_path(name)
            require(path.stat().st_size <= MAX_DEBUG, 'Diagnostic member exceeds bound')
            rows[name] = (path, file_record_allow_empty(path))
    inventory = {name: expected for name, (_, expected) in sorted(rows.items())}
    receipt = encoded({'schema': 1, 'diagnostics_only': True, 'qualification_authority': False,
                       'original_archive_included': False, 'files': inventory})
    require(rows and len(rows) < MAX_DEBUG_FILES and
            sum(row['bytes'] for _, row in rows.values()) + len(receipt) <= MAX_DEBUG,
            'Diagnostic evidence exceeds bound')
    output.mkdir(parents=True)
    for name, (source, expected) in sorted(rows.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with source.open('rb') as src, target.open('xb') as dst:
            for block in iter(lambda: src.read(CHUNK), b''):
                count += len(block)
                require(count <= expected['bytes'], 'Diagnostic input grew during staging')
                dst.write(block)
        require(file_record_allow_empty(target) == file_record_allow_empty(source) == expected,
                'Diagnostic input changed during staging')
    (output / 'diagnostics-only.json').write_bytes(receipt)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('fetch', 'extract', 'stage-evidence', 'stage-debug'))
    parser.add_argument('--contract', type=Path, default=CONTRACT)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--metadata-dir', type=Path)
    parser.add_argument('--restored-root', type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--qualifier-metadata', type=Path)
    parser.add_argument('--logs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--small', action='store_true')
    args = parser.parse_args()
    if args.operation == 'fetch':
        require(not args.small and args.archive is None and args.metadata_dir is None, 'Unexpected fetch arguments')
        fetch(contract(args.contract), args.output)
    elif args.operation == 'extract':
        require(args.archive is not None and args.metadata_dir is not None, 'Archive and official metadata are required')
        proof = verify_local(args.contract, args.archive, args.metadata_dir)
        require(args.small or str(args.output.absolute()) == proof.contract['original_root'], 'Full restoration must use original root')
        inventory = extract_verified(proof, args.output, SMALL_FILES if args.small else None)
        receipt = dict(proof.receipt, selected_file_inventory=inventory, extraction_mode='small' if args.small else 'full')
        # Never add a receipt to the original restored tree; keep it in the
        # separate evidence directory beside the original unchanged ZIP.
        target = args.metadata_dir / ('small-custody.json' if args.small else 'archive-custody.json')
        with target.open('xb') as output:
            output.write(encoded(receipt))
    elif args.operation == 'stage-evidence':
        require(not args.small and all((args.archive, args.metadata_dir, args.restored_root,
                args.candidate, args.qualifier_metadata, args.logs)), 'Complete recovery evidence inputs required')
        proof = verify_local(args.contract, args.archive, args.metadata_dir)
        stage_qualification(proof, args.restored_root, args.candidate, args.qualifier_metadata,
                            args.logs, args.metadata_dir, args.output)
    else:
        require(not args.small and all((args.metadata_dir, args.qualifier_metadata, args.logs)),
                'Diagnostic source directories are required')
        stage_debug(args.qualifier_metadata, args.logs, args.metadata_dir, args.output)
        print('Failure diagnostics preserved; this output confers no qualification authority.')
        return
    print('Archived producer bytes verified; no native/package build or device access.')


if __name__ == '__main__':
    main()
