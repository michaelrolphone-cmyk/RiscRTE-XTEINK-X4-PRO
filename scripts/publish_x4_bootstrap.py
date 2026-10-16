#!/usr/bin/env python3
"""Transport already-qualified .123 CI bytes. Never build or operate a device.

The finalized contract is a reviewed trust anchor, not a detached qualification.
Staging and publishing are separate gates; failed publication is never retried
by replacing an existing tag or asset.
"""
import argparse
import base64
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = 'michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO'
VERSION = '0.1.123'
TAG = 'test-native-provision-' + VERSION
BRANCH = 'work/x4-bootstrap-release-123'
WORKFLOW = '.github/workflows/native-provision-123.yml'
BASE = 'https://github.com/' + REPOSITORY + '/releases/download/' + TAG + '/'
SD = 'X4-0.1.121-Complete-SD-Keep-Existing.zip'
FACTORY = 'factory-candidate-erases-data-0x0.bin'
NATIVE = {FACTORY, 'firmware.bin', 'bootloader.bin', 'partitions.bin', 'store.bin', SD}
ROLES = {'product', 'runtime', 'system', 'drivers', 'sdk', 'image_helper', 'reader', 'utilities'}
ARTIFACT_ROLES = {'qualification', 'candidate', 'reproducibility'}
LIMITS = dict(publication_enabled=False, hardware_tested=False, device_accessed=False,
              version_reserved_by_recipe=False, factory_erases_data=True,
              preserving_update_kit_emitted=False, preserving_sdk_migration_eligible=False,
              sd_unchanged=True, device_msc_sd_workflow_preserved=True, feed_publication_pending=True)
STEPS = ('Product host and current Home integration gates',
         'Generic serial protocol storage and custody host gates',
         'Fresh .123 packages and native build with complete qualification',
         'Native artifact and workspace checks',
         'Preserve exact source SDK baseline package and build evidence',
         'Upload bounded qualification and startup receipts',
         'Upload candidate delivery assets', 'Upload complete reproducibility evidence')
MAX_ARCHIVE = 512 * 1024**2
MAX_EXPANSION = 1024 * 1024**2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def record(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def decode(raw):
    def unique(pairs):
        result = {}
        for name, value in pairs:
            require(name not in result, 'Duplicate JSON key')
            result[name] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def hex_value(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def positive(value):
    return type(value) is int and value > 0


def safe_name(name, flat=False):
    require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_./-]+', name), 'Unsafe file name')
    path = PurePosixPath(name)
    require(bool(path.parts) and not path.is_absolute() and '..' not in path.parts and str(path) == name and
            (not flat or len(path.parts) == 1), 'Noncanonical file name')
    return name


def valid_record(row):
    return (isinstance(row, dict) and set(row) == {'bytes', 'sha256'} and
            positive(row['bytes']) and hex_value(row['sha256']))


def final_contract(c, publish=False):
    require(c.get('schema') == 1 and c.get('finalized') is True, 'Contract is not finalized')
    require(type(c.get('publication_enabled')) is bool and
            (not publish or c['publication_enabled']), 'Publication is disabled')
    require(c['repository'] == REPOSITORY and c['version'] == VERSION and c['release_tag'] == TAG
            and c['publication_branch'] == BRANCH and c['feed_base_url'] == BASE, 'Release identity differs')
    require(hex_value(c['source_revision'], 40) and hex_value(c['source_tree'], 40), 'Exact product source required')
    require(set(c['sources']) == ROLES and c['sources']['product']['revision'] == c['source_revision'] and
            c['sources']['product']['tree'] == c['source_tree'], 'Product source lock differs')
    for row in c['sources'].values():
        require(set(row) == {'revision', 'tree', 'submodules'} and hex_value(row['revision'], 40) and
                hex_value(row['tree'], 40) and isinstance(row['submodules'], list) and
                all(isinstance(x, str) and re.fullmatch(r'[0-9a-f]{40} [^\r\n]+', x) for x in row['submodules']) and
                len(row['submodules']) == len(set(row['submodules'])), 'Invalid source pin')
    run = c['run']
    require(all(positive(run[k]) for k in ('id', 'attempt', 'workflow_id', 'job_id')) and
            run['event'] in ('push', 'workflow_dispatch', 'pull_request') and
            run['head_branch'] in ('work/x4-provision-123', 'work/native-provision-0.1.123', 'work/x4-bootstrap-0.1.123') and
            run['workflow_path'] == WORKFLOW and hex_value(run['workflow_sha256']), 'Exact producer run required')
    require((run['event'] == 'pull_request' and run.get('pull_request') == 45) or
            (run['event'] != 'pull_request' and run.get('pull_request') is None), 'Exact producer PR required')
    require(set(c['artifacts']) == ARTIFACT_ROLES, 'Three official artifact identities required')
    for role, row in c['artifacts'].items():
        require(set(row) == {'id', 'name', 'bytes', 'sha256'} and positive(row['id']) and
                positive(row['bytes']) and hex_value(row['sha256']) and
                row['name'] == 'x4-native-provision-123-' + role + '-' + c['source_revision'], 'Invalid artifact pin')
    require(len({row['id'] for row in c['artifacts'].values()}) == 3, 'Duplicate artifact IDs')
    for key in ('qualification_sha256', 'baseline_sha256', 'source_inputs_sha256', 'candidate_checksums_sha256'):
        require(hex_value(c[key]), 'Unresolved digest: ' + key)
    require(set(c['candidate_artifacts']) == NATIVE and
            all(valid_record(row) for row in c['candidate_artifacts'].values()), 'Incomplete candidate pins')
    require(c['candidate_artifacts'][FACTORY]['bytes'] == 16 * 1024**2, 'Factory must be exactly 16 MiB')
    require(isinstance(c['feed_files'], dict) and c['feed_files'] and
            all(valid_record(row) for row in c['feed_files'].values()), 'Missing exact feed inventory')
    for name in c['feed_files']:
        safe_name(name)
    return c


def verify_ci(c, run, jobs, artifacts, commit, workflow):
    expected = c['run']
    require(run['id'] == expected['id'] and run['run_attempt'] == expected['attempt'] and
            run['workflow_id'] == expected['workflow_id'] and run['path'] == WORKFLOW and
            run['head_sha'] == c['source_revision'] and run['head_branch'] == expected['head_branch'] and
            run['event'] == expected['event'] and run['status'] == 'completed' and
            run['conclusion'] == 'success', 'Producer run was not successful at exact source/attempt')
    require(run['repository']['full_name'] == run['head_repository']['full_name'] == REPOSITORY and
            run['repository']['id'] == run['head_repository']['id'],
            'Producer repository differs')
    # GitHub updates pull_requests[].head.sha when the PR advances. Historical
    # source identity comes from run/job/artifact head_sha, never that live field.
    if expected['event'] == 'pull_request':
        prs = run['pull_requests']
        require(len(prs) == 1 and prs[0]['number'] == expected['pull_request'] and
                hex_value(prs[0]['head']['sha'], 40) and
                prs[0]['head']['ref'] == expected['head_branch'] and
                prs[0]['head']['repo']['id'] == prs[0]['base']['repo']['id'] == run['repository']['id'],
                'Producer PR is not the exact same-repository source')
    require(commit['sha'] == c['source_revision'] and commit['commit']['tree']['sha'] == c['source_tree'],
            'Producer source tree differs')
    require(sha(workflow) == expected['workflow_sha256'], 'Producer workflow bytes differ')
    require(len(jobs) == 1 and jobs[0]['id'] == expected['job_id'] and jobs[0]['name'] == 'qualify' and
            jobs[0]['run_id'] == expected['id'] and jobs[0]['head_sha'] == c['source_revision'] and
            jobs[0]['status'] == 'completed' and jobs[0]['conclusion'] == 'success', 'Qualification job differs')
    for name in STEPS:
        rows = [row for row in jobs[0]['steps'] if row['name'] == name]
        require(len(rows) == 1 and rows[0]['status'] == 'completed' and rows[0]['conclusion'] == 'success',
                'Required qualification/upload step did not pass: ' + name)
    require(len(artifacts) == 3, 'Unexpected/duplicate split artifact set')
    for role, pin in c['artifacts'].items():
        rows = [row for row in artifacts if row['id'] == pin['id']]
        require(len(rows) == 1, 'Official artifact ID missing')
        row = rows[0]
        require(row['name'] == pin['name'] and row['size_in_bytes'] == pin['bytes'] and
                row.get('digest') == 'sha256:' + pin['sha256'] and row['expired'] is False and
                row['workflow_run']['id'] == expected['id'] and
                row['workflow_run']['head_sha'] == c['source_revision'] and
                row['workflow_run']['head_branch'] == expected['head_branch'] and
                row['workflow_run']['repository_id'] == row['workflow_run']['head_repository_id'] == run['repository']['id'],
                'Artifact provenance differs: ' + role)
        started, created, finished = (datetime.fromisoformat(value.replace('Z', '+00:00')) for value in
                                     (jobs[0]['started_at'], row['created_at'], jobs[0]['completed_at']))
        require(started.tzinfo is not None and created.tzinfo is not None and finished.tzinfo is not None and
                started <= created <= finished, 'Artifact is outside the exact successful run attempt')


def archive_files(raw):
    require(0 < len(raw) <= MAX_ARCHIVE, 'Archive exceeds bounded transport size')
    files, names, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.infolist()) <= 5000, 'Too many archive entries')
        for row in archive.infolist():
            name = row.filename[:-1] if row.is_dir() else row.filename
            safe_name(name)
            require(name not in names, 'Duplicate archive entry')
            names.add(name)
            mode = stat.S_IFMT(row.external_attr >> 16)
            require(mode in (0, stat.S_IFREG, stat.S_IFDIR) and not row.flag_bits & 1,
                    'Special or encrypted archive entry')
            if row.is_dir():
                require(row.file_size == 0 and mode != stat.S_IFREG, 'Invalid archive directory')
                continue
            require(mode != stat.S_IFDIR and row.file_size <= 256 * 1024**2, 'Invalid/oversized archive file')
            total += row.file_size
            require(total <= MAX_EXPANSION, 'Archive expansion exceeds bound')
            raw_file = archive.read(row)
            require(len(raw_file) == row.file_size, 'Archive entry size differs')
            files[name] = raw_file
    require(files, 'Empty archive')
    require(not any(any(parent.as_posix() in files for parent in PurePosixPath(name).parents
                        if parent.as_posix() != '.') for name in files), 'File/directory archive collision')
    return files


def verify_sums(raw, files):
    rows = {}
    for line in raw.decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_./-]+)', line)
        require(match is not None, 'Malformed checksums')
        digest, name = match.groups()
        safe_name(name)
        require(name not in rows, 'Duplicate checksum')
        rows[name] = digest
    require(set(rows) == set(files) and all(sha(files[name]) == digest for name, digest in rows.items()),
            'Incomplete or mismatched checksums')


def verify_feed(c, files, q):
    feed_files = {name[5:]: raw for name, raw in files.items() if name.startswith('feed/')}
    require({name: record(raw) for name, raw in feed_files.items()} == c['feed_files'] == q['feed']['files'],
            'Feed file inventory differs')
    require(q['feed']['base_url'] == BASE and q['feed']['catalog_url'] == BASE + 'native-packages-v1.json' and
            q['feed']['publication_enabled'] is False, 'Feed destination differs')
    require(feed_files['COMPLETE'] == b'riscrte.boot-profile-feed.v1\n', 'Incomplete feed output')
    # COMPLETE is written after the feed sums; candidate SHA256SUMS covers both.
    verify_sums(feed_files['SHA256SUMS'], {k: v for k, v in feed_files.items() if k not in ('SHA256SUMS', 'COMPLETE')})
    receipt = decode(feed_files['receipt.json'])
    feed = decode(feed_files['native-packages-v1.json'])
    require(receipt == q['feed']['receipt'] and receipt['published'] is False and
            receipt['credential_free'] is True and receipt['mirror_volume_instance'] == 9 and
            receipt['feed_sha256'] == sha(feed_files['native-packages-v1.json']) and
            receipt['feed_bytes'] == len(feed_files['native-packages-v1.json']), 'Feed receipt differs')
    require(feed['schema'] == 'riscrte.native-packages' and feed['version'] == 1 and
            feed['product'] == 'xteink-x4-pro' and feed['apps'] == [] and feed['profiles'] == {'core': []} and
            set(feed['boot_profiles']) == {'core'}, 'Wrong public feed')
    core = feed['boot_profiles']['core']
    require(core['native']['firmware_sha256'] == sha(files['firmware.bin']) and
            core['native']['firmware_size'] == len(files['firmware.bin']) and
            core['native']['runtime_version'] == '0.4.7' and core['native']['store_abi'] == 2,
            'Feed native binding differs')
    image = core['profile']['image']
    image_name = 'bootfs-' + sha(files['store.bin']) + '.bin'
    require(core['profile']['schema'] == 'riscrte.provisioning' and core['profile']['schema_version'] == 4 and
            image == {'url': BASE + image_name, 'bytes': len(files['store.bin']), 'sha256': sha(files['store.bin'])} and
            feed_files['assets/' + image_name] == files['store.bin'], 'Feed bootfs payload/URL differs')
    store = {name[6:]: raw for name, raw in files.items() if name.startswith('store/')}
    inventory = [[name, len(raw), sha(raw)] for name, raw in sorted(store.items())]
    require(core['profile']['files'] == inventory and receipt['file_count'] == len(store), 'Feed individual file inventory differs')
    require(len(core['mirrors']) == receipt['mirror_count'] and len(core['mirrors']) > 0, 'Empty mirror inventory')
    assets, mirror_paths = {image_name}, set()
    for mirror in core['mirrors']:
        name = 'image-' + mirror['sha256'] + '.elf'
        require(hex_value(mirror['sha256']) and mirror['url'] == BASE + name and
                positive(mirror['size']) and record(feed_files['assets/' + name]) ==
                {'bytes': mirror['size'], 'sha256': mirror['sha256']}, 'Empty/wrong mirror payload URL/hash')
        require(mirror['path'] not in mirror_paths and mirror['path'].startswith(('/Apps/', '/Drivers/')),
                'Duplicate/invalid individual mirror path')
        safe_name(mirror['path'][1:])
        mirror_paths.add(mirror['path']); assets.add(name)
    require(set(receipt['assets']) == assets and set(feed_files) ==
            {'native-packages-v1.json', 'receipt.json', 'SHA256SUMS', 'COMPLETE'} | {'assets/' + n for n in assets},
            'Unexpected/omitted feed asset')
    for name, row in receipt['assets'].items():
        require(record(feed_files['assets/' + name]) == {'bytes': row['size'], 'sha256': row['sha256']},
                'Feed asset receipt differs')
    return {'native-packages-v1.json': feed_files['native-packages-v1.json'],
            **{name: feed_files['assets/' + name] for name in assets}}


def verify_candidate(c, files, evidence, baseline, source_inputs):
    require(sha(files['qualification.json']) == c['qualification_sha256'] and
            sha(files['SHA256SUMS']) == c['candidate_checksums_sha256'], 'Candidate report/checksum pin differs')
    verify_sums(files['SHA256SUMS'], {k: v for k, v in files.items() if k != 'SHA256SUMS'})
    q, lock = decode(files['qualification.json']), decode(files['source-lock.json'])
    require(q['schema'] == 1 and q['status'] == 'software-qualified-candidate-hardware-pending', 'Qualification did not succeed')
    for name, value in LIMITS.items():
        require(q.get(name) is value, 'Qualification limit differs: ' + name)
    require(lock['schema'] == 1 and lock['publication_enabled'] is False and lock['candidate_version'] == VERSION and
            q['input_lock'] == lock and q['input_lock_sha256'] == sha(files['source-lock.json']) and
            lock['sources'] == c['sources'], 'Qualified source lock differs')
    require(sha(baseline) == c['baseline_sha256'] == lock['baseline_contract_sha256'] and
            decode(baseline) == q['baseline_contract'], 'Released baseline identity differs')
    require(sha(source_inputs) == c['source_inputs_sha256'], 'Producer dependency input differs')
    inputs = decode(source_inputs)
    require(inputs['candidate_version'] == VERSION and inputs['feed_base_url'] == BASE and
            set(inputs['sources']) == ROLES - {'product', 'sdk'} and
            all(c['sources'][role]['revision'] == row['revision'] for role, row in inputs['sources'].items()),
            'Dependency source selection differs')
    for name in ('qualification.json', 'source-lock.json', 'SHA256SUMS', 'serial-product-normal.json', 'serial-product-sanitized.json'):
        require(files[name] == evidence['candidate/' + name], 'Split qualification/candidate evidence differs')
    require(evidence['build/native-build-evidence/source-lock.json'] == files['source-lock.json'] and
            sha(evidence['metadata/workflow.yml']) == c['run']['workflow_sha256'], 'Archived producer/source lock differs')
    for role, row in c['sources'].items():
        require(evidence['source-evidence/' + role + '-identity.txt'].decode().strip() ==
                row['revision'] + ' ' + row['tree'] and not evidence['source-evidence/' + role + '-status.txt'].strip(),
                'Unclean or mismatched archived source: ' + role)
    closure = q['build_closure']
    require(closure['sources'] == lock['sources'] and closure['fresh_build'] is True and
            closure['same_process_qualification'] is True and closure['compile_jobs'] == 1 and
            closure['detached_receipt_is_attestation'] is False, 'Controlled build closure differs')
    require(q['artifacts'] == c['candidate_artifacts'] and all(record(files[name]) == row
            for name, row in c['candidate_artifacts'].items()), 'Candidate payload bytes differ')
    for name, key in (('firmware.bin', 'firmware_bin'), ('bootloader.bin', 'bootloader'), ('partitions.bin', 'partitions')):
        row = lock['native_files'][key]
        require(record(files[name]) == {k: row[k] for k in ('bytes', 'sha256')} == closure['artifacts'][key],
                'Linked native payload differs')
    factory = files[FACTORY]
    require(len(factory) == 0x1000000 and len(files['store.bin']) == 0x510000 and
            0 < len(files['bootloader.bin']) <= 0x8000 and 0 < len(files['partitions.bin']) <= 0x1000 and
            0 < len(files['firmware.bin']) <= 0x260000, 'Factory/component geometry differs')
    for offset, name in ((0, 'bootloader.bin'), (0x8000, 'partitions.bin'), (0x10000, 'firmware.bin'), (0x2f0000, 'store.bin')):
        require(factory[offset:offset + len(files[name])] == files[name], 'Factory component hash/placement differs')
    base = decode(baseline)
    require(record(files[SD]) == {key: base['sd'][key] for key in ('bytes', 'sha256')}, 'Complete SD archive changed')
    for name, count, sanitized in (('admission', 43, False), ('admission_sanitized', 43, True),
                                    ('sd_admission', 49, False), ('sd_admission_sanitized', 49, True)):
        row = q[name]
        require(row['elf_count'] == count and row['sanitized'] is sanitized and
                row['target_instructions_executed'] is False and
                row['native_elf_sha256'] == lock['native_files']['firmware_elf']['sha256'], 'Incomplete final ELF admission')
        if not name.startswith('sd_'):
            require(row['prepared'] is True and row['cohort_validated'] is True and
                    row['hardware_calls'] == row['storage_calls'] == 0 and
                    row['retained_sd_graph_binding']['production_graph_binding_passed'] is True, 'Retained graph admission failed')
    require(q['native']['elf_bin_identical'] is True and q['native']['platform_capacity']['value'] == 40 and
            q['preservation_software_model']['passed'] is True and
            q['payload_preservation']['sd_archive_unchanged'] is True and
            q['payload_preservation']['old_grants_preserved'] is True and
            q['unchanged_store_payloads'] == 101, 'Native/payload preservation qualification missing')
    required = NATIVE | {'qualification.json', 'source-lock.json', 'SHA256SUMS',
                         'serial-product-normal.json', 'serial-product-sanitized.json'}
    require({name for name in files if not name.startswith(('feed/', 'store/'))} == required,
            'Unexpected candidate delivery output')
    store = {name[6:]: raw for name, raw in files.items() if name.startswith('store/')}
    changed = {'boot.json', 'cohort.json', 'default.elf', 'default.json',
               'installed-apps/driver.elf', 'installed-apps/manifest.json'}
    preserved = q['payload_preservation']
    require(set(store) == set(base['files']) and len(store) == base['store_file_count'] == 107 and
            set(preserved['changed']) == changed and len(preserved['changed']) == 6 and
            preserved['unchanged_count'] == 101 and set(preserved['unchanged']) == set(store) - changed,
            'Retained individual store file inventory differs')
    for name in set(store) - changed:
        require(record(store[name]) == {key: base['files'][name][key] for key in ('bytes', 'sha256')} and
                sha(store[name]) == preserved['unchanged'][name], 'Retained individual store file changed')
    return verify_feed(c, files, q)


class Github:
    def json(self, endpoint, method='GET', body=None):
        args = ['gh', 'api', '--method', method, endpoint]
        if body is not None:
            args += ['--input', '-']
        result = subprocess.run(args, input=None if body is None else encoded(body),
                                stdout=subprocess.PIPE, check=True, timeout=120)
        return decode(result.stdout)

    def pages(self, endpoint, field=None):
        rows = []
        for page in range(1, 101):
            result = self.json(endpoint + ('&' if '?' in endpoint else '?') + 'per_page=100&page=' + str(page))
            batch = result[field] if field else result
            require(isinstance(batch, list), 'Invalid paged API response')
            rows.extend(batch)
            if len(batch) < 100:
                require(not field or len(rows) == result['total_count'], 'Incomplete API pagination')
                return rows
        raise ValueError('API pagination exceeds bound')

    def download(self, endpoint, target, max_bytes, accept=None):
        command = ['gh', 'api', endpoint]
        if accept:
            command += ['-H', 'Accept: ' + accept]
        with target.open('xb') as out, subprocess.Popen(command, stdout=subprocess.PIPE) as process:
            count = 0
            try:
                for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
                    count += len(block)
                    require(count <= max_bytes, 'Download exceeds pinned byte bound')
                    out.write(block)
                require(process.wait(timeout=120) == 0, 'Artifact download failed')
            except BaseException:
                process.kill(); process.wait()
                raise

    def public_download(self, url, target, max_bytes):
        require(url.startswith(BASE) and safe_name(url[len(BASE):], flat=True), 'Unapproved public URL')
        # No token, cookie jar, .netrc, credential handler or environment proxy.
        class HttpsOnly(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                parsed = urllib.parse.urlsplit(newurl)
                require(parsed.scheme == 'https' and not parsed.username and not parsed.password,
                        'Insecure/credential-bearing public redirect')
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), HttpsOnly())
        start, count = time.monotonic(), 0
        with opener.open(url, timeout=60) as response, target.open('xb') as output:
            require(response.status == 200, 'Public download did not succeed')
            for block in iter(lambda: response.read(1024 * 1024), b''):
                count += len(block)
                require(count <= max_bytes and time.monotonic() - start <= 180,
                        'Public download exceeds byte/time bound')
                output.write(block)

    def command(self, *args):
        subprocess.run(['gh', *map(str, args)], check=True, timeout=600)


def source_file(api, revision, name):
    row = api.json('repos/' + REPOSITORY + '/contents/' + name + '?ref=' + revision)
    require(row['type'] == 'file' and row['encoding'] == 'base64' and row['path'] == name,
            'Exact source file unavailable')
    return base64.b64decode(row['content'], validate=False)


def official_inputs(api, c):
    prefix = 'repos/' + REPOSITORY
    attempt = prefix + '/actions/runs/%d/attempts/%d' % (c['run']['id'], c['run']['attempt'])
    run = api.json(attempt)
    jobs = api.pages(attempt + '/jobs', 'jobs')
    artifacts = api.pages(prefix + '/actions/runs/%d/artifacts' % c['run']['id'], 'artifacts')
    commit = api.json(prefix + '/commits/' + c['source_revision'])
    workflow = source_file(api, c['source_revision'], WORKFLOW)
    verify_ci(c, run, jobs, artifacts, commit, workflow)
    return {'ci-run.json': encoded(run), 'ci-jobs.json': encoded(jobs),
            'ci-artifacts.json': encoded(artifacts), 'source-commit.json': encoded(commit)}


def verify_output(output, checksum_sha, publisher_sha):
    require(hex_value(checksum_sha) and hex_value(publisher_sha, 40), 'Exact staged identity required')
    require(output.is_dir() and not output.is_symlink(), 'Unsafe output directory')
    files = {}
    for path in output.iterdir():
        safe_name(path.name, flat=True)
        require(path.is_file() and not path.is_symlink(), 'Nonregular release asset')
        files[path.name] = path.read_bytes()
    require(sha(files['SHA256SUMS']) == checksum_sha, 'Staged checksum identity differs')
    verify_sums(files['SHA256SUMS'], {k: v for k, v in files.items() if k != 'SHA256SUMS'})
    release = decode(files['release.json'])
    c = final_contract(decode(files['transport-contract.json']))
    require(release['publisher_revision'] == publisher_sha and release['compiled_product_revision'] == c['source_revision'] and
            release['release_tag'] == TAG and release['rebuilt'] is False and release['evidence_repacked'] is False and
            release['limits'] == LIMITS and release['assets'] ==
            {k: record(v) for k, v in files.items() if k not in ('release.json', 'SHA256SUMS')}, 'Output custody differs')
    require(b'erases internal saved settings and data' in files['RELEASE-NOTES.txt'], 'Factory erasure warning missing')
    return c, files


def stage(contract_path, publisher_sha, output, api=None):
    contract_bytes = contract_path.read_bytes()
    c = final_contract(decode(contract_bytes))
    require(hex_value(publisher_sha, 40) and not output.exists(), 'Exact publisher revision and new output required')
    api = api or Github()
    metadata = official_inputs(api, c)
    baseline = source_file(api, c['source_revision'], 'docs/native-provision-123/released-baseline.json')
    inputs = source_file(api, c['source_revision'], 'docs/native-provision-123/source-inputs.json')
    with tempfile.TemporaryDirectory(prefix='x4-bootstrap-transport-') as temporary:
        archives = {}
        for role in ('qualification', 'candidate'):
            pin = c['artifacts'][role]
            require(pin['bytes'] <= MAX_ARCHIVE, 'Pinned archive exceeds transport size bound')
            target = Path(temporary) / (role + '.zip')
            api.download('repos/' + REPOSITORY + '/actions/artifacts/%d/zip' % pin['id'], target, pin['bytes'])
            raw = target.read_bytes()
            require(record(raw) == {k: pin[k] for k in ('bytes', 'sha256')}, 'Downloaded artifact digest differs')
            archives[role] = raw
        files = archive_files(archives['candidate'])
        evidence = archive_files(archives['qualification'])
        feed = verify_candidate(c, files, evidence, baseline, inputs)
        assets = {name: files[name] for name in NATIVE}
        assets.update(feed)
        assets.update({name: files[name] for name in ('qualification.json', 'source-lock.json',
                                                     'serial-product-normal.json', 'serial-product-sanitized.json')})
        assets.update(metadata)
        assets.update({'candidate-evidence.zip': archives['candidate'], 'qualification-evidence.zip': archives['qualification'],
                       'transport-contract.json': contract_bytes, 'feed-receipt.json': files['feed/receipt.json']})
    assets['RELEASE-NOTES.txt'] = ("X4 0.1.123 native ESP-IDF 6.1 provisioning bootstrap candidate\n\n"
        "Software-qualified; hardware testing is pending.\n"
        "WARNING: flashing factory-candidate-erases-data-0x0.bin at 0x0 erases internal saved settings and data.\n"
        "The factory image is exactly 16 MiB. No preserving migration or OTA kit is supplied.\n"
        "Separate firmware.bin, bootloader.bin, partitions.bin and store.bin are exact evidence;\n"
        "they are not an independent flashing procedure. Boot, health confirmation and rollback remain hardware-pending.\n"
        "The complete SD ZIP is the unchanged released 0.1.121 package. Merge/replace only matching paths;\n"
        "do not format the card or delete unrelated books, ROMs, saves or settings.\n"
        "Individual feed mirrors retain their admitted paths and exact bytes. Ordinary file writes preserve unrelated paths.\n"
        "The selected device-MSC SD workflow is retained. RTEF1 is not a firmware flashing or package installer protocol.\n"
        "The original candidate and qualification ZIPs are copied byte-for-byte. Reproducibility artifact custody is pinned in the contract.\n"
        "A later paired firmware/full-payload release requires confirmed installation of this bootstrap.\n\n"
        "Feed: " + BASE + "native-packages-v1.json\n").encode()
    assets['release.json'] = encoded(dict(schema=1, release_tag=TAG, publisher_revision=publisher_sha,
        compiled_product_revision=c['source_revision'], producer_run=c['run'], artifacts=c['artifacts'],
        rebuilt=False, evidence_repacked=False, limits=LIMITS, assets={k: record(v) for k, v in sorted(assets.items())}))
    assets['SHA256SUMS'] = ''.join(sha(raw) + '  ' + name + '\n' for name, raw in sorted(assets.items())).encode()
    output.mkdir(parents=True)
    for name, raw in assets.items():
        safe_name(name, flat=True)
        (output / name).write_bytes(raw)
    verify_output(output, sha(assets['SHA256SUMS']), publisher_sha)
    return sha(assets['SHA256SUMS'])


def no_existing_target(api):
    refs = api.json('repos/' + REPOSITORY + '/git/matching-refs/tags/' + TAG)
    require(isinstance(refs, list) and not any(row['ref'] == 'refs/tags/' + TAG for row in refs),
            'Reserved tag already exists; refusing to replace any identity')
    releases = api.pages('repos/' + REPOSITORY + '/releases')
    require(not any(row['tag_name'] == TAG for row in releases), 'Release already exists; refusing to replace assets')


def verify_remote(api, release, files, c, *, draft):
    require(release['tag_name'] == TAG and release['draft'] is draft and release['prerelease'] is True,
            'Published release identity/state differs')
    ref = api.json('repos/' + REPOSITORY + '/git/ref/tags/' + TAG)
    require(ref['ref'] == 'refs/tags/' + TAG and ref['object']['type'] == 'commit' and
            ref['object']['sha'] == c['source_revision'], 'Published tag no longer names qualified product source')
    assets = api.pages('repos/' + REPOSITORY + '/releases/%d/assets' % release['id'])
    require(len(assets) == len(files) and {row['name'] for row in assets} == set(files), 'Remote release asset set differs')
    with tempfile.TemporaryDirectory(prefix='x4-bootstrap-readback-') as temporary:
        for row in assets:
            name = safe_name(row['name'], flat=True)
            require(row['state'] == 'uploaded' and row['size'] == len(files[name]) and
                    row.get('browser_download_url') == BASE + name, 'Remote asset size/URL differs')
            if row.get('digest') is not None:
                require(row['digest'] == 'sha256:' + sha(files[name]), 'Remote asset digest differs')
            path = Path(temporary) / name
            if draft:
                api.download('repos/' + REPOSITORY + '/releases/assets/%d' % row['id'], path, len(files[name]),
                             accept='application/octet-stream')
            else:
                api.public_download(row['browser_download_url'], path, len(files[name]))
            require(path.read_bytes() == files[name], 'Redownloaded release bytes differ: ' + name)


def publish(contract_path, publisher_sha, output, checksum_sha, api=None):
    approved = final_contract(decode(contract_path.read_bytes()), publish=True)
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY and
            os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH and
            os.environ.get('GITHUB_SHA') == publisher_sha and os.environ.get('GITHUB_EVENT_NAME') == 'push',
            'Publication requires the exact approved branch push')
    c, files = verify_output(output, checksum_sha, publisher_sha)
    require(c == approved and files['transport-contract.json'] == contract_path.read_bytes(), 'Staged contract differs')
    api = api or Github()
    official_inputs(api, c)  # Recheck official successful source/run/artifact metadata before mutation.
    no_existing_target(api)
    ref = api.json('repos/' + REPOSITORY + '/git/refs', method='POST',
                   body={'ref': 'refs/tags/' + TAG, 'sha': c['source_revision']})
    require(ref['ref'] == 'refs/tags/' + TAG and ref['object']['type'] == 'commit' and
            ref['object']['sha'] == c['source_revision'], 'Created tag differs')
    # A failed upload/readback remains a draft. Never overwrite or silently resume an existing target.
    api.command('release', 'create', TAG, '--repo', REPOSITORY, '--verify-tag', '--target', c['source_revision'],
                '--draft', '--prerelease', '--latest=false', '--title', 'X4 0.1.123 native provisioning bootstrap (hardware pending)',
                '--notes-file', str(output / 'RELEASE-NOTES.txt'))
    api.command('release', 'upload', TAG, *[str(output / name) for name in sorted(files)], '--repo', REPOSITORY)
    # The tag-name endpoint is documented for published releases. Authenticated
    # listings include drafts; bind the unique created release ID before upload verification.
    drafts = [row for row in api.pages('repos/' + REPOSITORY + '/releases') if row['tag_name'] == TAG]
    require(len(drafts) == 1 and positive(drafts[0]['id']), 'Created draft identity is ambiguous')
    release = drafts[0]
    release_id = release['id']
    verify_remote(api, release, files, c, draft=True)
    api.command('release', 'edit', TAG, '--repo', REPOSITORY, '--draft=false', '--prerelease', '--latest=false')
    release = api.json('repos/' + REPOSITORY + '/releases/tags/' + TAG)
    require(release['id'] == release_id, 'Published release ID changed')
    verify_remote(api, release, files, c, draft=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('stage', 'verify', 'publish'))
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--publisher-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checksum-sha')
    args = parser.parse_args()
    if args.operation == 'stage':
        print(stage(args.contract, args.publisher_sha, args.output))
    elif args.operation == 'verify':
        verify_output(args.output, args.checksum_sha, args.publisher_sha)
    else:
        publish(args.contract, args.publisher_sha, args.output, args.checksum_sha)


if __name__ == '__main__':
    main()
