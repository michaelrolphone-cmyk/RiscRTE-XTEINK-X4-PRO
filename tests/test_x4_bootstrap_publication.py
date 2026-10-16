#!/usr/bin/env python3
"""Synthetic publisher guards. No native builds, network, publication or device I/O."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publish_x4_bootstrap as p

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = 'f' * 40


def sums(files):
    return ''.join(p.sha(raw) + '  ' + name + '\n' for name, raw in sorted(files.items())).encode()


def zipped(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            archive.writestr(name, raw)
    return out.getvalue()


def fixture():
    sources = {role: {'revision': '%040x' % (i + 1), 'tree': '%040x' % (i + 30), 'submodules': []}
               for i, role in enumerate(sorted(p.ROLES))}
    c = dict(schema=1, finalized=True, publication_enabled=False, repository=p.REPOSITORY,
             version=p.VERSION, release_tag=p.TAG, publication_branch=p.BRANCH, feed_base_url=p.BASE,
             source_revision=sources['product']['revision'], source_tree=sources['product']['tree'], sources=sources,
             run=dict(id=11, attempt=1, workflow_id=12, job_id=13, event='push',
                      head_branch='work/x4-provision-123', workflow_path=p.WORKFLOW, workflow_sha256=p.sha(b'workflow')))
    files = {'firmware.bin': b'firmware', 'bootloader.bin': b'bootloader', 'partitions.bin': b'partitions',
             'store.bin': bytes(0x510000), p.SD: b'unchanged original SD ZIP',
             'serial-product-normal.json': b'{"sanitized":false}\n',
             'serial-product-sanitized.json': b'{"sanitized":true}\n'}
    factory = bytearray(0x1000000)
    for at, name in ((0, 'bootloader.bin'), (0x8000, 'partitions.bin'), (0x10000, 'firmware.bin'), (0x2f0000, 'store.bin')):
        factory[at:at+len(files[name])] = files[name]
    files[p.FACTORY] = bytes(factory)
    changed = {'boot.json', 'cohort.json', 'default.elf', 'default.json',
               'installed-apps/driver.elf', 'installed-apps/manifest.json'}
    store = {name: b'new-' + name.encode() for name in changed}
    store.update({'retained/file-%03d.bin' % n: ('same-%d' % n).encode() for n in range(101)})
    baseline = {'sd': p.record(files[p.SD]), 'store_file_count': 107,
                'files': {name: p.record(raw if name not in changed else b'old-' + name.encode()) for name, raw in store.items()}}
    baseline_bytes = p.encoded(baseline)
    source_inputs = p.encoded(dict(candidate_version=p.VERSION, feed_base_url=p.BASE,
        sources={role: {'revision': row['revision']} for role, row in sources.items() if role not in ('sdk', 'product')}))
    lock = dict(schema=1, publication_enabled=False, candidate_version=p.VERSION, sources=sources,
                baseline_contract_sha256=p.sha(baseline_bytes), native_files={})
    for name, key in (('firmware.bin', 'firmware_bin'), ('bootloader.bin', 'bootloader'), ('partitions.bin', 'partitions')):
        lock['native_files'][key] = {'path': name, **p.record(files[name])}
    lock['native_files']['firmware_elf'] = {'path': 'native.elf', **p.record(b'elf')}
    files['source-lock.json'] = p.encoded(lock)
    q = dict(schema=1, status='software-qualified-candidate-hardware-pending', **p.LIMITS,
             input_lock=lock, input_lock_sha256=p.sha(files['source-lock.json']), baseline_contract=baseline,
             artifacts={name: p.record(files[name]) for name in p.NATIVE},
             build_closure=dict(sources=sources, fresh_build=True, same_process_qualification=True,
                                compile_jobs=1, detached_receipt_is_attestation=False,
                                artifacts={key: {k: row[k] for k in ('bytes', 'sha256')} for key, row in lock['native_files'].items()}),
             native={'elf_bin_identical': True, 'platform_capacity': {'value': 40}},
             preservation_software_model={'passed': True}, unchanged_store_payloads=101,
             payload_preservation=dict(sd_archive_unchanged=True, old_grants_preserved=True,
                 changed=sorted(changed), unchanged_count=101,
                 unchanged={name: p.sha(raw) for name, raw in store.items() if name not in changed}))
    for name, count, sanitized in (('admission', 43, False), ('admission_sanitized', 43, True),
                                  ('sd_admission', 49, False), ('sd_admission_sanitized', 49, True)):
        q[name] = dict(elf_count=count, sanitized=sanitized, target_instructions_executed=False,
                       native_elf_sha256=p.sha(b'elf'), prepared=True, cohort_validated=True,
                       hardware_calls=0, storage_calls=0,
                       retained_sd_graph_binding={'production_graph_binding_passed': True})
    image_name = 'bootfs-' + p.sha(files['store.bin']) + '.bin'
    mirror = b'mirror'
    mirror_name = 'image-' + p.sha(mirror) + '.elf'
    feed = dict(schema='riscrte.native-packages', version=1, product='xteink-x4-pro', apps=[], profiles={'core': []},
                boot_profiles={'core': dict(native={'firmware_sha256': p.sha(files['firmware.bin']),
                    'firmware_size': len(files['firmware.bin']), 'runtime_version': '0.4.7', 'store_abi': 2},
                    profile={'schema': 'riscrte.provisioning', 'schema_version': 4,
                        'image': {'url': p.BASE + image_name, **p.record(files['store.bin'])},
                        'files': [[name, len(raw), p.sha(raw)] for name, raw in sorted(store.items())]},
                    mirrors=[{'url': p.BASE + mirror_name, 'sha256': p.sha(mirror), 'size': len(mirror),
                              'path': '/Drivers/test/' + mirror_name, 'driver': True}])})
    feed_raw = p.encoded(feed)
    receipt = dict(published=False, credential_free=True, mirror_volume_instance=9,
                   feed_sha256=p.sha(feed_raw), feed_bytes=len(feed_raw), file_count=len(store), mirror_count=1,
                   assets={name: {'size': len(raw), 'sha256': p.sha(raw)} for name, raw in
                           ((image_name, files['store.bin']), (mirror_name, mirror))})
    ff = {'native-packages-v1.json': feed_raw, 'receipt.json': p.encoded(receipt),
          'assets/' + image_name: files['store.bin'], 'assets/' + mirror_name: mirror}
    ff['SHA256SUMS'] = sums(ff)
    ff['COMPLETE'] = b'riscrte.boot-profile-feed.v1\n'
    q['feed'] = dict(base_url=p.BASE, catalog_url=p.BASE + 'native-packages-v1.json', publication_enabled=False,
                     receipt=receipt, files={name: p.record(raw) for name, raw in ff.items()})
    files.update({'store/' + name: raw for name, raw in store.items()})
    files.update({'feed/' + name: raw for name, raw in ff.items()})
    files['qualification.json'] = p.encoded(q)
    files['SHA256SUMS'] = sums(files)
    evidence = {'candidate/' + name: files[name] for name in
                ('qualification.json', 'source-lock.json', 'SHA256SUMS', 'serial-product-normal.json', 'serial-product-sanitized.json')}
    evidence['metadata/workflow.yml'] = b'workflow'
    evidence['build/native-build-evidence/source-lock.json'] = files['source-lock.json']
    for role, row in sources.items():
        evidence['source-evidence/' + role + '-identity.txt'] = (row['revision'] + ' ' + row['tree'] + '\n').encode()
        evidence['source-evidence/' + role + '-status.txt'] = b''
    archives = {'candidate': zipped(files), 'qualification': zipped(evidence), 'reproducibility': b'large retained evidence'}
    c.update(qualification_sha256=p.sha(files['qualification.json']), baseline_sha256=p.sha(baseline_bytes),
             source_inputs_sha256=p.sha(source_inputs), candidate_checksums_sha256=p.sha(files['SHA256SUMS']),
             candidate_artifacts=q['artifacts'], feed_files=q['feed']['files'],
             artifacts={role: {'id': i+20, 'name': 'x4-native-provision-123-' + role + '-' + c['source_revision'],
                              **p.record(archives[role])} for i, role in enumerate(sorted(p.ARTIFACT_ROLES))})
    run = dict(id=11, run_attempt=1, workflow_id=12, path=p.WORKFLOW, head_sha=c['source_revision'],
                head_branch=c['run']['head_branch'], event='push', status='completed', conclusion='success',
                repository={'full_name': p.REPOSITORY, 'id': 99}, head_repository={'full_name': p.REPOSITORY, 'id': 99})
    jobs = [dict(id=13, name='qualify', run_id=11, head_sha=c['source_revision'], status='completed', conclusion='success',
                 started_at='2026-10-16T20:00:00Z', completed_at='2026-10-16T21:00:00Z',
                 steps=[dict(name=name, status='completed', conclusion='success') for name in p.STEPS])]
    artifacts = [dict(id=row['id'], name=row['name'], size_in_bytes=row['bytes'], digest='sha256:' + row['sha256'],
                      expired=False, created_at='2026-10-16T20:59:00Z',
                      workflow_run={'id': 11, 'head_sha': c['source_revision'], 'head_branch': c['run']['head_branch'],
                                    'repository_id': 99, 'head_repository_id': 99})
                 for row in c['artifacts'].values()]
    commit = {'sha': c['source_revision'], 'commit': {'tree': {'sha': c['source_tree']}}}
    return dict(c=c, files=files, evidence=evidence, baseline=baseline_bytes, inputs=source_inputs, archives=archives,
                run=run, jobs=jobs, artifacts=artifacts, commit=commit, workflow=b'workflow')


def refresh(f, *, feed=False):
    files, c = f['files'], f['c']
    q = p.decode(files['qualification.json'])
    if feed:
        ff = {k[5:]: v for k, v in files.items() if k.startswith('feed/')}
        ff['SHA256SUMS'] = sums({k: v for k, v in ff.items() if k not in ('COMPLETE', 'SHA256SUMS')})
        q['feed']['files'] = c['feed_files'] = {k: p.record(v) for k, v in ff.items()}
        q['feed']['receipt'] = p.decode(ff['receipt.json'])
        files.update({'feed/' + k: v for k, v in ff.items()})
    files['qualification.json'] = p.encoded(q)
    files['SHA256SUMS'] = sums({k: v for k, v in files.items() if k != 'SHA256SUMS'})
    c['qualification_sha256'] = p.sha(files['qualification.json'])
    c['candidate_checksums_sha256'] = p.sha(files['SHA256SUMS'])
    for name in ('qualification.json', 'source-lock.json', 'SHA256SUMS', 'serial-product-normal.json', 'serial-product-sanitized.json'):
        f['evidence']['candidate/' + name] = files[name]


def verify(f):
    return p.verify_candidate(f['c'], f['files'], f['evidence'], f['baseline'], f['inputs'])


class FakeGithub:
    def __init__(self, f):
        self.f = f
        self.calls = []
        self.tag = None
        self.release = None
        self.assets = {}
        self.corrupt_readback = False
        self.bad_source = False
        self.public_unavailable = False
        self.mutate_evidence_on_create = False
        self.mutate_evidence_on_upload = False

    def json(self, endpoint, method='GET', body=None):
        self.calls.append((method, endpoint, body))
        c = self.f['c']
        prefix = 'repos/' + p.REPOSITORY
        if method == 'POST':
            assert endpoint == prefix + '/git/refs'
            assert self.tag is None
            self.tag = {'ref': body['ref'], 'object': {'type': 'commit', 'sha': body['sha']}}
            return self.tag
        if '/contents/' in endpoint:
            name = endpoint.split('/contents/')[1].split('?')[0]
            raw = {p.WORKFLOW: self.f['workflow'], 'docs/native-provision-123/released-baseline.json': self.f['baseline'],
                   'docs/native-provision-123/source-inputs.json': self.f['inputs']}[name]
            return dict(type='file', encoding='base64', path=name, content=base64.b64encode(raw).decode())
        if '/actions/runs/' in endpoint:
            return {**self.f['run'], 'head_sha': '0'*40} if self.bad_source else self.f['run']
        if '/commits/' in endpoint:
            return self.f['commit']
        if '/git/matching-refs/' in endpoint:
            return [self.tag] if self.tag else []
        if '/git/ref/tags/' in endpoint:
            return self.tag
        if '/releases/tags/' in endpoint:
            return self.release
        raise AssertionError(endpoint)

    def pages(self, endpoint, field=None):
        if '/jobs' in endpoint:
            return self.f['jobs']
        if '/actions/runs/' in endpoint and '/artifacts' in endpoint:
            return self.f['artifacts']
        if re_match := __import__('re').search(r'/releases/([0-9]+)/assets$', endpoint):
            return [dict(id=i+1, name=name, state='uploaded', size=len(raw), digest='sha256:' + p.sha(raw),
                         browser_download_url=p.BASE+name) for i, (name, raw) in enumerate(sorted(self.assets.items()))]
        if endpoint.endswith('/releases'):
            return [self.release] if self.release else []
        raise AssertionError(endpoint)

    def download(self, endpoint, target, max_bytes, accept=None):
        self.calls.append(('DOWNLOAD', endpoint, None))
        if '/actions/artifacts/' in endpoint:
            artifact_id = int(endpoint.split('/actions/artifacts/')[1].split('/')[0])
            role = next(k for k, v in self.f['c']['artifacts'].items() if v['id'] == artifact_id)
            raw = self.f['archives'][role]
        else:
            asset_id = int(endpoint.rsplit('/', 1)[1])
            raw = sorted(self.assets.items())[asset_id-1][1]
            if self.corrupt_readback:
                raw = b'wrong bytes'
        assert len(raw) <= max_bytes
        target.write_bytes(raw)

    def public_download(self, url, target, max_bytes):
        self.calls.append(('PUBLIC', url, None))
        if self.public_unavailable:
            raise ValueError('Public URL unavailable although authenticated API succeeded')
        assert url.startswith(p.BASE)
        raw = self.assets[url[len(p.BASE):]]
        assert len(raw) <= max_bytes
        target.write_bytes(raw)

    def command(self, *args):
        self.calls.append(('COMMAND', args, None))
        if args[:2] == ('release', 'create'):
            assert self.tag['object']['sha'] == self.f['c']['source_revision']
            assert '--draft' in args and '--verify-tag' in args
            self.release = dict(id=1, tag_name=p.TAG, draft=True, prerelease=True)
            if self.mutate_evidence_on_create:
                (Path(args[args.index('--notes-file') + 1]).parent / p.REPRODUCIBILITY).write_bytes(b'changed after verification')
        elif args[:2] == ('release', 'upload'):
            assert '--clobber' not in args
            for path in args[3:args.index('--repo')]:
                path = Path(path)
                assert path.name not in self.assets
                if self.mutate_evidence_on_upload and path.name == p.REPRODUCIBILITY:
                    path.write_bytes(b'changed during upload')
                self.assets[path.name] = path.read_bytes()
        elif args[:2] == ('release', 'edit'):
            self.release['draft'] = False
        else:
            raise AssertionError(args)


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = fixture()

    def setUp(self):
        self.f = copy.deepcopy(self.original)

    def test_complete_synthetic_custody(self):
        p.final_contract(self.f['c'])
        p.verify_ci(self.f['c'], self.f['run'], self.f['jobs'], self.f['artifacts'], self.f['commit'], self.f['workflow'])
        out = verify(self.f)
        self.assertIn('native-packages-v1.json', out)
        self.assertTrue(any(name.startswith('bootfs-') for name in out))

    def test_pending_contract_cannot_stage_or_publish(self):
        disabled = copy.deepcopy(self.f['c'])
        disabled.update(finalized=False, publication_enabled=False, disabled_reason='Pending qualification')
        for publish in (False, True):
            with self.assertRaisesRegex(ValueError, 'not finalized'):
                p.final_contract(disabled, publish=publish)
        with self.assertRaisesRegex(ValueError, 'disabled'):
            p.final_contract(self.f['c'], publish=True)

    def test_committed_contract_is_either_complete_or_explicitly_disabled(self):
        c = p.decode((ROOT / 'release/x4-bootstrap-123/contract.json').read_bytes())
        self.assertIs(type(c['finalized']), bool)
        self.assertIs(type(c['publication_enabled']), bool)
        if c['finalized']:
            p.final_contract(c)
        else:
            self.assertFalse(c['publication_enabled'])
            self.assertTrue(c['disabled_reason'])

    def test_missing_contract_pin_rejected(self):
        for field in ('source_revision', 'source_tree', 'qualification_sha256', 'baseline_sha256',
                      'source_inputs_sha256', 'candidate_checksums_sha256'):
            c = copy.deepcopy(self.f['c']); c[field] = None
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.final_contract(c)
        for field in ('id', 'attempt', 'job_id', 'workflow_id', 'workflow_sha256'):
            c = copy.deepcopy(self.f['c']); c['run'][field] = None
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.final_contract(c)

    def test_wrong_release_target_rejected(self):
        for field in ('repository', 'version', 'release_tag', 'publication_branch', 'feed_base_url'):
            c = copy.deepcopy(self.f['c']); c[field] = 'unapproved'
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.final_contract(c)

    def test_same_repository_pr45_source_allowed(self):
        f = self.f
        f['c']['run'].update(event='pull_request', pull_request=45, head_branch='work/x4-bootstrap-0.1.123')
        f['run'].update(event='pull_request', head_branch='work/x4-bootstrap-0.1.123')
        f['run']['repository']['id'] = 99
        pr = dict(number=45, head={'sha': f['c']['source_revision'], 'ref': 'work/x4-bootstrap-0.1.123', 'repo': {'id': 99}},
                  base={'repo': {'id': 99}})
        f['run']['pull_requests'] = [pr]
        for row in f['artifacts']:
            row['workflow_run']['head_branch'] = 'work/x4-bootstrap-0.1.123'
        p.final_contract(f['c'])
        p.verify_ci(f['c'], f['run'], f['jobs'], f['artifacts'], f['commit'], f['workflow'])
        pr['head']['sha'] = 'e' * 40  # Live PR advances; immutable run/job/artifact heads remain pinned.
        p.verify_ci(f['c'], f['run'], f['jobs'], f['artifacts'], f['commit'], f['workflow'])
        for key, value in (('sha', 'invalid'), ('ref', 'wrong'), ('repo', {'id': 7})):
            saved = pr['head'][key]; pr['head'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.verify_ci(f['c'], f['run'], f['jobs'], f['artifacts'], f['commit'], f['workflow'])
            pr['head'][key] = saved

    def test_failed_running_wrong_attempt_or_source_ci_rejected(self):
        for field, value in (('conclusion', 'failure'), ('status', 'in_progress'), ('run_attempt', 2),
                             ('head_sha', '0'*40), ('head_branch', 'wrong'), ('workflow_id', 99), ('path', 'other.yml')):
            run = {**self.f['run'], field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.verify_ci(self.f['c'], run, self.f['jobs'], self.f['artifacts'], self.f['commit'], self.f['workflow'])

    def test_incomplete_qualification_job_rejected(self):
        for field, value in (('conclusion', 'skipped'), ('status', 'in_progress')):
            jobs = copy.deepcopy(self.f['jobs']); jobs[0]['steps'][3][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.verify_ci(self.f['c'], self.f['run'], jobs, self.f['artifacts'], self.f['commit'], self.f['workflow'])

    def test_artifact_mismatch_and_duplicate_rejected(self):
        for field, value in (('id', 0), ('name', 'wrong'), ('size_in_bytes', 1), ('digest', 'sha256:'+'0'*64), ('expired', True),
                             ('created_at', '2026-10-16T19:59:00Z'), ('created_at', '2026-10-16T21:01:00Z')):
            artifacts = copy.deepcopy(self.f['artifacts']); artifacts[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.verify_ci(self.f['c'], self.f['run'], self.f['jobs'], artifacts, self.f['commit'], self.f['workflow'])
        with self.assertRaises(ValueError):
            p.verify_ci(self.f['c'], self.f['run'], self.f['jobs'], self.f['artifacts']*2, self.f['commit'], self.f['workflow'])

    def test_source_tree_workflow_and_fork_mismatch_rejected(self):
        for key in ('commit', 'workflow', 'run'):
            f = copy.deepcopy(self.f)
            if key == 'commit': f['commit']['commit']['tree']['sha'] = '0'*40
            if key == 'workflow': f['workflow'] += b'changed'
            if key == 'run': f['run']['head_repository']['full_name'] = 'outside/fork'
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.verify_ci(f['c'], f['run'], f['jobs'], f['artifacts'], f['commit'], f['workflow'])

    def test_candidate_hash_and_checksum_mutations_rejected(self):
        for name in ('firmware.bin', 'qualification.json', 'SHA256SUMS', 'store/retained/file-001.bin'):
            f = copy.deepcopy(self.f); f['files'][name] += b'changed'
            with self.subTest(name=name), self.assertRaises(ValueError): verify(f)

    def test_report_safety_limits_rejected_even_with_rehashed_sums(self):
        for key in p.LIMITS:
            f = copy.deepcopy(self.f)
            q = p.decode(f['files']['qualification.json']); q[key] = not q[key]
            f['files']['qualification.json'] = p.encoded(q); refresh(f)
            with self.subTest(key=key), self.assertRaises(ValueError): verify(f)

    def test_split_evidence_mismatch_rejected(self):
        for key in ('candidate/qualification.json', 'candidate/source-lock.json', 'metadata/workflow.yml',
                    'source-evidence/product-identity.txt', 'source-evidence/runtime-status.txt'):
            f = copy.deepcopy(self.f); f['evidence'][key] += b'changed'
            with self.subTest(key=key), self.assertRaises(ValueError): verify(f)

    def test_factory_component_and_exact_16mib_guards(self):
        for replacement in (self.f['files'][p.FACTORY][:-1], b'bad' + self.f['files'][p.FACTORY][3:]):
            f = copy.deepcopy(self.f); f['files'][p.FACTORY] = replacement
            q = p.decode(f['files']['qualification.json'])
            q['artifacts'][p.FACTORY] = f['c']['candidate_artifacts'][p.FACTORY] = p.record(replacement)
            f['files']['qualification.json'] = p.encoded(q); refresh(f)
            with self.assertRaises(ValueError): verify(f)

    def test_complete_sd_preservation_rejected_even_if_rehashed(self):
        f = self.f; f['files'][p.SD] += b'changed'
        q = p.decode(f['files']['qualification.json'])
        q['artifacts'][p.SD] = f['c']['candidate_artifacts'][p.SD] = p.record(f['files'][p.SD])
        f['files']['qualification.json'] = p.encoded(q); refresh(f)
        with self.assertRaisesRegex(ValueError, 'Complete SD archive changed'): verify(f)

    def test_unrelated_individual_store_file_change_rejected(self):
        f = self.f; f['files']['store/retained/file-001.bin'] += b'changed'; refresh(f)
        with self.assertRaisesRegex(ValueError, 'Retained individual store file changed'): verify(f)

    def test_blank_and_wrong_feed_payload_urls_rejected(self):
        for target in ('image', 'mirror'):
            for value in ('', 'https://other.invalid/payload', p.BASE + 'wrong.bin'):
                f = copy.deepcopy(self.f)
                feed = p.decode(f['files']['feed/native-packages-v1.json'])
                row = feed['boot_profiles']['core']['profile']['image'] if target == 'image' else feed['boot_profiles']['core']['mirrors'][0]
                row['url'] = value
                raw = p.encoded(feed); f['files']['feed/native-packages-v1.json'] = raw
                receipt = p.decode(f['files']['feed/receipt.json']); receipt.update(feed_sha256=p.sha(raw), feed_bytes=len(raw))
                f['files']['feed/receipt.json'] = p.encoded(receipt); refresh(f, feed=True)
                with self.subTest(target=target, value=value), self.assertRaises(ValueError): verify(f)

    def test_feed_asset_missing_or_changed_rejected(self):
        name = next(k for k in self.f['files'] if k.startswith('feed/assets/image-'))
        for removed in (False, True):
            f = copy.deepcopy(self.f)
            if removed: del f['files'][name]
            else: f['files'][name] += b'changed'
            refresh(f, feed=True)
            with self.subTest(removed=removed), self.assertRaises((ValueError, KeyError)): verify(f)

    def test_unknown_candidate_file_or_preserving_kit_rejected(self):
        f = self.f; f['files']['preserving-update.zip'] = b'not allowed'; refresh(f)
        with self.assertRaisesRegex(ValueError, 'Unexpected candidate'): verify(f)

    def test_unsafe_archive_paths_duplicates_symlinks_and_collisions_rejected(self):
        for name in ('../x', '/x', '.', 'x//y', 'x/./y', 'x\\y', 'x:y'):
            with self.subTest(name=name), self.assertRaises(ValueError): p.archive_files(zipped({name: b'x'}))
        for kind in ('duplicate', 'symlink', 'fifo', 'collision'):
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w') as archive:
                if kind == 'duplicate':
                    archive.writestr('x', b'a'); archive.writestr('x', b'b')
                elif kind == 'collision':
                    archive.writestr('x', b'a'); archive.writestr('x/y', b'b')
                else:
                    info = zipfile.ZipInfo('x'); info.external_attr = ((stat.S_IFLNK if kind == 'symlink' else stat.S_IFIFO) | 0o777) << 16
                    archive.writestr(info, b'target')
            with self.subTest(kind=kind), self.assertRaises(ValueError): p.archive_files(output.getvalue())

    def test_archive_expansion_bound_and_duplicate_json(self):
        with patch.object(p, 'MAX_EXPANSION', 1), self.assertRaisesRegex(ValueError, 'expansion'):
            p.archive_files(zipped({'x': b'xx'}))
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'): p.decode(b'{"x":1,"x":2}')

    def stage_fixture(self, root, enabled=False):
        self.f['c']['publication_enabled'] = enabled
        contract = root / 'contract.json'; contract.write_bytes(p.encoded(self.f['c']))
        api = FakeGithub(self.f)
        output = root / 'output'
        checksum = p.stage(contract, PUBLISHER, output, api)
        return contract, api, output, checksum

    def environment(self):
        return patch.dict(os.environ, GITHUB_REPOSITORY=p.REPOSITORY, GITHUB_REF='refs/heads/' + p.BRANCH,
                          GITHUB_SHA=PUBLISHER, GITHUB_EVENT_NAME='push')

    def test_stage_original_archives_sd_feed_and_warnings_without_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            contract, api, output, checksum = self.stage_fixture(Path(directory))
            p.verify_output(output, checksum, PUBLISHER)
            self.assertEqual((output / 'candidate-evidence.zip').read_bytes(), self.f['archives']['candidate'])
            self.assertEqual((output / 'qualification-evidence.zip').read_bytes(), self.f['archives']['qualification'])
            self.assertEqual((output / p.REPRODUCIBILITY).read_bytes(), self.f['archives']['reproducibility'])
            self.assertEqual((output / p.SD).read_bytes(), self.f['files'][p.SD])
            self.assertEqual((output / 'native-packages-v1.json').read_bytes(), self.f['files']['feed/native-packages-v1.json'])
            notes = (output / 'RELEASE-NOTES.txt').read_text()
            self.assertIn('erases internal saved settings and data', notes)
            self.assertIn('do not format the card or delete unrelated', notes)
            self.assertFalse(any(row[0] in ('POST', 'COMMAND') for row in api.calls))
            self.assertEqual(sum(row[0] == 'DOWNLOAD' for row in api.calls), 3)

    def test_reproducibility_is_opaque_streamed_and_not_loaded_in_memory(self):
        # The fixture's reproducibility bytes deliberately are not a ZIP. They
        # must be preserved opaquely and never be passed to the ZIP parser.
        original = Path.read_bytes
        def read_small(path):
            if path.name == p.REPRODUCIBILITY:
                raise AssertionError('Complete evidence must be streamed, never read_bytes()')
            return original(path)
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'read_bytes', read_small):
            _, _, output, checksum = self.stage_fixture(Path(directory))
            _, files = p.verify_output(output, checksum, PUBLISHER)
            self.assertIsInstance(files[p.REPRODUCIBILITY], Path)
            self.assertEqual(p.file_record(files[p.REPRODUCIBILITY]), p.record(self.f['archives']['reproducibility']))

    def test_complete_evidence_digest_and_bound_fail_closed(self):
        self.f['archives']['reproducibility'] = b'wrong'
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'reproducibility artifact digest'):
            self.stage_fixture(Path(directory))
        c = copy.deepcopy(self.f['c']); c['artifacts']['reproducibility']['bytes'] = p.MAX_EVIDENCE + 1
        with self.assertRaisesRegex(ValueError, 'artifact pin'): p.final_contract(c)

    def test_streaming_file_hash_and_size_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'opaque'; path.write_bytes(b'original evidence')
            self.assertEqual(p.file_record(path), p.record(b'original evidence'))
            with self.assertRaisesRegex(ValueError, 'bound'): p.file_record(path, limit=2)

    def test_mismatched_downloaded_artifact_rejected(self):
        self.f['archives']['candidate'] += b'changed'
        with tempfile.TemporaryDirectory() as directory, self.assertRaises((ValueError, AssertionError)):
            self.stage_fixture(Path(directory))

    def test_output_checksum_asset_set_source_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, output, checksum = self.stage_fixture(Path(directory))
            for digest, publisher in (('0'*64, PUBLISHER), (checksum, '0'*40)):
                with self.assertRaises(ValueError): p.verify_output(output, digest, publisher)
            extra = output / 'unexpected'; extra.write_bytes(b'extra')
            with self.assertRaises(ValueError): p.verify_output(output, checksum, PUBLISHER)
            extra.unlink(); extra.symlink_to(output / 'firmware.bin')
            with self.assertRaises(ValueError): p.verify_output(output, checksum, PUBLISHER)

    def test_publish_tag_points_to_producer_and_every_asset_read_back_twice(self):
        with tempfile.TemporaryDirectory() as directory, self.environment():
            contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=True)
            p.publish(contract, PUBLISHER, output, checksum, api)
            self.assertEqual(api.tag['object']['sha'], self.f['c']['source_revision'])
            self.assertNotEqual(api.tag['object']['sha'], PUBLISHER)
            self.assertFalse(api.release['draft'])
            self.assertEqual(sum(row[0] == 'DOWNLOAD' for row in api.calls), 3 + len(api.assets))
            self.assertEqual(sum(row[0] == 'PUBLIC' for row in api.calls), len(api.assets))
            commands = [row[1] for row in api.calls if row[0] == 'COMMAND']
            self.assertEqual([row[1] for row in commands], ['create', 'upload', 'edit'])

    def test_existing_tag_and_release_are_never_replaced(self):
        for kind in ('tag', 'release'):
            with tempfile.TemporaryDirectory() as directory, self.environment():
                contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=True)
                if kind == 'tag': api.tag = {'ref': 'refs/tags/' + p.TAG, 'object': {'type': 'commit', 'sha': '0'*40}}
                else: api.release = {'tag_name': p.TAG, 'draft': True}
                with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'already exists'):
                    p.publish(contract, PUBLISHER, output, checksum, api)
                self.assertFalse(any(row[0] in ('POST', 'COMMAND') for row in api.calls))

    def test_corrupt_draft_readback_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory, self.environment():
            contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=True)
            api.corrupt_readback = True
            with self.assertRaises((ValueError, AssertionError)):
                p.publish(contract, PUBLISHER, output, checksum, api)
            self.assertTrue(api.release['draft'])
            self.assertFalse(any(row[0] == 'COMMAND' and row[1][:2] == ('release', 'edit') for row in api.calls))

    def test_complete_evidence_mutation_after_verification_never_publishes(self):
        for when in ('create', 'upload'):
            with self.subTest(when=when), tempfile.TemporaryDirectory() as directory, self.environment():
                contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=True)
                setattr(api, 'mutate_evidence_on_' + when, True)
                with self.assertRaises(ValueError):
                    p.publish(contract, PUBLISHER, output, checksum, api)
                self.assertTrue(api.release['draft'])
                self.assertFalse(any(row[0] == 'COMMAND' and row[1][:2] == ('release', 'edit') for row in api.calls))
                if when == 'create':
                    self.assertFalse(api.assets)

    def test_authenticated_success_does_not_mask_unavailable_public_feed(self):
        with tempfile.TemporaryDirectory() as directory, self.environment():
            contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=True)
            api.public_unavailable = True
            with self.assertRaisesRegex(ValueError, 'Public URL unavailable'):
                p.publish(contract, PUBLISHER, output, checksum, api)
            self.assertFalse(api.release['draft'])
            self.assertEqual(sum(row[0] == 'DOWNLOAD' for row in api.calls), 3 + len(api.assets))
            self.assertEqual(sum(row[0] == 'PUBLIC' for row in api.calls), 1)

    def test_public_transport_rejects_wrong_origin_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            for url in ('http://github.com/unsafe', 'https://other.invalid/file', p.BASE + '../escape'):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    p.Github().public_download(url, Path(directory) / 'out', 10)

    def test_changed_live_provenance_blocks_mutations(self):
        with tempfile.TemporaryDirectory() as directory, self.environment():
            contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=True)
            api.bad_source = True
            with self.assertRaises(ValueError): p.publish(contract, PUBLISHER, output, checksum, api)
            self.assertFalse(any(row[0] in ('POST', 'COMMAND') for row in api.calls))

    def test_publish_requires_enabled_contract_and_exact_publisher_push(self):
        with tempfile.TemporaryDirectory() as directory, self.environment():
            contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=False)
            with self.assertRaisesRegex(ValueError, 'disabled'): p.publish(contract, PUBLISHER, output, checksum, api)
        with tempfile.TemporaryDirectory() as directory, self.environment():
            contract, api, output, checksum = self.stage_fixture(Path(directory), enabled=True)
            with patch.dict(os.environ, GITHUB_EVENT_NAME='pull_request'), self.assertRaisesRegex(ValueError, 'branch push'):
                p.publish(contract, PUBLISHER, output, checksum, api)
            self.assertFalse(any(row[0] in ('POST', 'COMMAND') for row in api.calls))

    def test_staging_review_upload_is_exact_and_separate_from_full_evidence(self):
        text = (ROOT / '.github/workflows/x4-bootstrap-release-123.yml').read_text()
        stage = text.split('  stage:\n', 1)[1].split('  publish:\n', 1)[0]
        review = stage.split('      - name: Upload bounded staging-review metadata\n', 1)[1]
        paths = review.split('          path: |\n', 1)[1].split('          if-no-files-found:', 1)[0]
        self.assertEqual(paths.split(), ['release-assets/release.json', 'release-assets/SHA256SUMS',
                                        'release-assets/transport-contract.json', 'release-assets/RELEASE-NOTES.txt'])
        self.assertIn('name: x4-bootstrap-staging-review-${{ github.sha }}', review)
        self.assertIn('if-no-files-found: error', review)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02', review)
        self.assertIn('name: x4-bootstrap-publication-${{ github.sha }}', stage)
        self.assertIn('path: release-assets/*', stage)
        self.assertNotIn('staging-review', text.split('  publish:\n', 1)[1])

    def test_workflow_has_no_native_build_and_separate_write_gate(self):
        text = (ROOT / '.github/workflows/x4-bootstrap-release-123.yml').read_text()
        self.assertIn('contents: write', text)
        self.assertIn("needs.guards.outputs.publication_enabled == 'true'", text)
        self.assertIn('branches: [work/x4-bootstrap-release-123]', text)
        for forbidden in ('idf.py', 'native_provision_build.py', '--clobber', 'workflow_run:'):
            self.assertNotIn(forbidden, text)
        producer = (ROOT / p.WORKFLOW).read_text()
        self.assertNotIn('work/x4-bootstrap-release-123', producer)


if __name__ == '__main__':
    unittest.main()
