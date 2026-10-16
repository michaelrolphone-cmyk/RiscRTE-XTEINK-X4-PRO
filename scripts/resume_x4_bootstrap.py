#!/usr/bin/env python3
"""Resume only a pinned, fully uploaded draft; never create or upload assets."""
import argparse
import hashlib
import os
import re
from pathlib import Path
import stat
import tempfile
import zipfile
import publish_x4_bootstrap as p

MODE = 'verify-existing-exact-draft-and-promote'
WORKFLOW = '.github/workflows/x4-bootstrap-release-123.yml'
MAX_TRANSPORT = 2 * 1024**3 - 1
MAX_TOTAL = 2 * 1024**3 - 1
PREFIX = 'repos/' + p.REPOSITORY


def validate_contract(r, c):
    p.final_contract(c, publish=True)
    p.require(set(r) == {'schema', 'enabled', 'mode', 'release', 'stage', 'checksum_sha256',
                         'transport_contract_sha256', 'assets'} and r['schema'] == 1 and
              r['enabled'] is True and r['mode'] == MODE and
              p.hex_value(r['checksum_sha256']) and p.hex_value(r['transport_contract_sha256']),
              'Exact enabled resume contract required')
    release = r['release']
    prefix = 'https://github.com/' + p.REPOSITORY + '/releases/tag/'
    p.require(set(release) == {'id', 'tag_name', 'target_commitish', 'html_url', 'created_at'} and
              p.positive(release['id']) and release['tag_name'] == p.TAG and
              release['target_commitish'] == c['source_revision'] and
              release['html_url'].startswith(prefix) and
              re.fullmatch('untagged-[0-9a-f]+', release['html_url'][len(prefix):]) and
              isinstance(release['created_at'], str), 'Exact existing draft identity required')
    stage = r['stage']; run = stage['run']
    p.require(set(stage) == {'publisher_revision', 'publisher_tree', 'run', 'artifacts'} and
              p.hex_value(stage['publisher_revision'], 40) and p.hex_value(stage['publisher_tree'], 40) and
              set(run) == {'id', 'attempt', 'workflow_id', 'guard_job_id', 'stage_job_id', 'publish_job_id', 'workflow_sha256'} and
              all(p.positive(run[k]) for k in ('id', 'attempt', 'workflow_id', 'guard_job_id', 'stage_job_id', 'publish_job_id')) and
              len({run[k] for k in ('guard_job_id', 'stage_job_id', 'publish_job_id')}) == 3 and
              p.hex_value(run['workflow_sha256']) and set(stage['artifacts']) == {'transport', 'review'},
              'Exact original publication staging required')
    for role, marker in (('transport', 'publication'), ('review', 'staging-review')):
        pin = stage['artifacts'][role]
        p.recovery.artifact_pin(pin, 'x4-bootstrap-' + marker + '-' + stage['publisher_revision'],
                                MAX_TRANSPORT if role == 'transport' else p.MAX_ARCHIVE)
    p.require(stage['artifacts']['transport']['id'] != stage['artifacts']['review']['id'], 'Duplicate staging artifact ID')
    assets = r['assets']
    p.require(isinstance(assets, dict) and 0 < len(assets) <= 256 and
              {p.REPRODUCIBILITY, 'release.json', 'SHA256SUMS', 'transport-contract.json'} <= assets.keys(),
              'Exact complete asset inventory required')
    for name, row in assets.items():
        p.safe_name(name, flat=True)
        p.require(set(row) == {'id', 'bytes', 'sha256'} and p.positive(row['id']) and
                  p.valid_record({k: row[k] for k in ('bytes', 'sha256')}) and
                  row['bytes'] <= (p.MAX_EVIDENCE if name == p.REPRODUCIBILITY else p.MAX_ARCHIVE),
                  'Invalid resume asset identity')
    p.require(len({row['id'] for row in assets.values()}) == len(assets) and
              sum(row['bytes'] for row in assets.values()) <= MAX_TOTAL and
              assets['SHA256SUMS']['sha256'] == r['checksum_sha256'] and
              assets['transport-contract.json']['sha256'] == r['transport_contract_sha256'] and
              {k: assets[p.REPRODUCIBILITY][k] for k in ('bytes', 'sha256')} ==
              {k: c['artifacts']['reproducibility'][k] for k in ('bytes', 'sha256')},
              'Resume asset checksum/size authority differs')
    return r


def verify_stage(api, r):
    stage, expected = r['stage'], r['stage']['run']
    endpoint = PREFIX + '/actions/runs/%d/attempts/%d' % (expected['id'], expected['attempt'])
    run = api.json(endpoint)
    p.require(run['id'] == expected['id'] and run['run_attempt'] == expected['attempt'] and
              run['workflow_id'] == expected['workflow_id'] and run['path'] == WORKFLOW and
              run['head_sha'] == stage['publisher_revision'] and run['head_branch'] == p.BRANCH and
              run['event'] == 'push' and run['status'] == 'completed' and run['conclusion'] == 'failure' and
              run['repository']['full_name'] == run['head_repository']['full_name'] == p.REPOSITORY and
              run['repository']['id'] == run['head_repository']['id'] == 1408146704,
              'Original publication attempt differs')
    commit = api.json(PREFIX + '/commits/' + stage['publisher_revision'])
    p.require(commit['sha'] == stage['publisher_revision'] and commit['commit']['tree']['sha'] == stage['publisher_tree'] and
              p.sha(p.source_file(api, stage['publisher_revision'], WORKFLOW)) == expected['workflow_sha256'],
              'Original publisher source differs')
    jobs = api.pages(endpoint + '/jobs', 'jobs')
    p.require(len(jobs) == 3 and {j['name'] for j in jobs} == {'guards', 'stage', 'publish'}, 'Original job set differs')
    for name, key, conclusion in (('guards', 'guard_job_id', 'success'), ('stage', 'stage_job_id', 'success'),
                                  ('publish', 'publish_job_id', 'failure')):
        job = next(j for j in jobs if j['name'] == name)
        p.require(job['id'] == expected[key] and job['run_id'] == expected['id'] and
                  job['run_attempt'] == expected['attempt'] and job['head_sha'] == stage['publisher_revision'] and
                  job['status'] == 'completed' and job['conclusion'] == conclusion, 'Original staging job differs')
        if name == 'publish':
            p.require([s['name'] for s in job['steps'] if s['conclusion'] == 'failure'] ==
                      ['Create source-exact draft, verify all uploaded bytes, publish and verify again'],
                      'Original publication failure differs')
        else:
            p.require(job['steps'] and all(s['status'] == 'completed' and s['conclusion'] == 'success' for s in job['steps']),
                      'Original successful staging steps differ')
    artifacts = api.pages(PREFIX + '/actions/runs/%d/artifacts' % expected['id'], 'artifacts')
    p.require(len(artifacts) == 2, 'Original staging artifact set differs')
    job = next(j for j in jobs if j['name'] == 'stage')
    for pin in stage['artifacts'].values():
        p.recovery.verify_artifact(pin, artifacts, run, job, {'id': expected['id'], 'head_branch': p.BRANCH})


def restore_transport(archive_path, output, r):
    pin = {k: r['stage']['artifacts']['transport'][k] for k in ('bytes', 'sha256')}
    p.require(archive_path.is_file() and not any(path.is_symlink() for path in
              (archive_path, output, *archive_path.parents, *output.parents)),
              'Symlinked transport archive or output parent')
    p.require(p.file_record(archive_path) == pin and pin['bytes'] <= MAX_TRANSPORT and not output.exists(),
              'Original transport ZIP identity or new output differs')
    expected = r['assets']
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        p.require(len(entries) == len(expected) and len({e.filename for e in entries}) == len(entries) and
                  {e.filename for e in entries} == set(expected), 'Transport ZIP membership differs')
        total = 0
        for entry in entries:
            p.safe_name(entry.filename, flat=True)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            p.require(entry.orig_filename == entry.filename and
                      entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                      not entry.is_dir() and mode in (0, stat.S_IFREG) and not entry.flag_bits & 1 and
                      entry.file_size == expected[entry.filename]['bytes'], 'Unsafe transport ZIP entry')
            total += entry.file_size
        p.require(total <= MAX_TOTAL, 'Transport ZIP expansion exceeds bound')
        output.mkdir(parents=True)
        for entry in entries:
            size, digest = 0, hashlib.sha256()
            with archive.open(entry) as source, (output / entry.filename).open('xb') as target:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    size += len(block)
                    p.require(size <= expected[entry.filename]['bytes'], 'Transport entry exceeds pinned size')
                    digest.update(block); target.write(block)
            p.require({'bytes': size, 'sha256': digest.hexdigest()} ==
                      {k: expected[entry.filename][k] for k in ('bytes', 'sha256')}, 'Transport entry digest differs')
    p.require(p.file_record(archive_path) == pin, 'Original transport ZIP changed during extraction')


def verify_target(api, r, c, *, draft):
    release = api.json(PREFIX + '/releases/%d' % r['release']['id'])
    p.require(all(release[k] == r['release'][k] for k in ('id', 'tag_name', 'target_commitish', 'created_at')) and
              release['draft'] is draft and release['prerelease'] is True and
              (not draft or release['html_url'] == r['release']['html_url']), 'Exact existing release differs')
    ref = api.json(PREFIX + '/git/ref/tags/' + p.TAG)
    p.require(ref['ref'] == 'refs/tags/' + p.TAG and ref['object']['type'] == 'commit' and
              ref['object']['sha'] == c['source_revision'], 'Existing qualified tag differs')
    assets = api.pages(PREFIX + '/releases/%d/assets' % release['id'])
    p.require(len(assets) == len(r['assets']) and {a['name'] for a in assets} == set(r['assets']),
              'Existing asset set differs')
    for asset in assets:
        expected = r['assets'][asset['name']]
        p.require(asset['id'] == expected['id'] and asset['state'] == 'uploaded' and
                  asset['size'] == expected['bytes'] and asset['digest'] == 'sha256:' + expected['sha256'],
                  'Existing asset identity differs')
    return release


def resume(contract_path, resume_path, publisher_sha, output, api=None):
    raw = contract_path.read_bytes(); c = p.final_contract(p.decode(raw), publish=True)
    r = validate_contract(p.decode(resume_path.read_bytes()), c)
    p.require(p.sha(raw) == r['transport_contract_sha256'] and p.hex_value(publisher_sha, 40) and
              os.environ.get('GITHUB_SHA') == publisher_sha and os.environ.get('GITHUB_EVENT_NAME') == 'push' and
              os.environ.get('GITHUB_REPOSITORY') == p.REPOSITORY and
              os.environ.get('GITHUB_REF') == 'refs/heads/' + p.BRANCH, 'Exact resume branch/source required')
    api = api or p.Github()
    verify_stage(api, r)
    p.official_inputs(api, c)
    verify_target(api, r, c, draft=True)
    with tempfile.TemporaryDirectory(prefix='x4-resume-transport-') as temp:
        path = Path(temp) / 'original-transport.zip'
        pin = r['stage']['artifacts']['transport']
        api.download(PREFIX + '/actions/artifacts/%d/zip' % pin['id'], path, pin['bytes'])
        restore_transport(path, output, r)
    checked, files = p.verify_output(output, r['checksum_sha256'], r['stage']['publisher_revision'])
    p.require(checked == c and files['transport-contract.json'] == raw and set(files) == set(r['assets']) and
              all(p.record(files[n]) == {k: row[k] for k in ('bytes', 'sha256')} for n, row in r['assets'].items()),
              'Original staged asset records differ')
    release = verify_target(api, r, c, draft=True)
    p.verify_remote(api, release, files, c, draft=True)
    verify_target(api, r, c, draft=True)  # Reject asset replacement during readback.
    result = api.json(PREFIX + '/releases/%d' % r['release']['id'], method='PATCH',
                      body={'draft': False, 'prerelease': True, 'make_latest': 'false'})
    p.require(result['id'] == r['release']['id'] and result['draft'] is False, 'Promoted release differs')
    release = verify_target(api, r, c, draft=False)
    p.verify_remote(api, release, files, c, draft=False)
    verify_target(api, r, c, draft=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('contract', 'resume', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--publisher-sha', required=True)
    args = parser.parse_args()
    resume(args.contract, args.resume, args.publisher_sha, args.output)


if __name__ == '__main__':
    main()
