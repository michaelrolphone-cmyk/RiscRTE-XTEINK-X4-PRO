"""Explicit split-run custody for qualification of unchanged compiled X4 bytes."""
from datetime import datetime
import hashlib
import json
import re

MODE = 'verified-ci-archive-later-process-qualification'
WORKFLOW = '.github/workflows/native-provision-123-requalify.yml'
BRANCH = 'work/x4-qualification-recovery-123'
REPOSITORY = 'michaelrolphone-cmyk/RiscRTE-XTEINK-X4-PRO'
STEPS = (
    'Clone exact separate qualification source', 'Archive recovery guard tests',
    'Verify exact producer attempt and download original ZIP',
    'Export bounded original admission inputs', 'Upload bounded original admission inputs',
    'Restore unchanged producer archive at original paths',
    'Restore exact source and compiler custody without building',
    'Qualification-only host regression gates',
    'Qualify exact archived native and package bytes without rebuilding',
    'Stage bounded original and recovery qualification evidence',
    'Upload recovered candidate delivery assets',
    'Upload bounded recovery qualification and source evidence')
ALLOWED_FILES = {
    '.github/workflows/native-provision-123-requalify.yml',
    'docs/native-provision-123/archive-input.json', 'docs/native-provision-123/README.md',
    'scripts/native_provision_archive.py', 'scripts/native_provision_requalify.py',
    'scripts/native_provision_candidate.py', 'scripts/native_provision_qualification.py',
    'scripts/native_provision_payloads.py',
    'tests/test_native_provision_archive.py', 'tests/test_native_provision_requalify.py',
    'tests/test_native_provision_candidate.py',
}
EXTRA_FILES = {'archive-recovery.json', 'archive-contract.json',
               'original-build-closure.json', 'original-package-build-receipt.json'}
ORIGINAL_RECEIPTS = {
    'build/native-build-evidence/source-lock.json': 'source-lock.json',
    'build/native-build-evidence/build-closure.json': 'original-build-closure.json',
    'build-packages/package-build-receipt.json': 'original-package-build-receipt.json',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hex_value(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def artifact_pin(pin, name, bound):
    require(isinstance(pin, dict) and set(pin) == {'id', 'name', 'bytes', 'sha256'} and
            type(pin['id']) is int and pin['id'] > 0 and type(pin['bytes']) is int and
            0 < pin['bytes'] <= bound and pin['name'] == name and hex_value(pin['sha256']),
            'Invalid split recovery artifact pin')


def contract(c, archive_bound):
    r = c['qualification_recovery']
    require(set(r) == {'schema', 'mode', 'source_revision', 'source_tree', 'run',
                      'custody_receipt_sha256', 'archive_contract_sha256',
                      'producer_qualification_artifact', 'admission_inputs_artifact'} and
            r['schema'] == 1 and r['mode'] == MODE and
            hex_value(r['source_revision'], 40) and hex_value(r['source_tree'], 40) and
            r['source_revision'] != c['source_revision'] and
            hex_value(r['custody_receipt_sha256']) and hex_value(r['archive_contract_sha256']),
            'Exact later-process qualification identity required')
    run = r['run']
    require(set(run) == {'id', 'attempt', 'workflow_id', 'job_id', 'event', 'head_branch',
                        'workflow_path', 'workflow_sha256'} and
            all(type(run[k]) is int and run[k] > 0 for k in ('id', 'attempt', 'workflow_id', 'job_id')) and
            run['id'] != c['run']['id'] and run['event'] == 'push' and
            run['head_branch'] == BRANCH and run['workflow_path'] == WORKFLOW and
            hex_value(run['workflow_sha256']), 'Exact recovery run required')
    artifact_pin(r['producer_qualification_artifact'],
                 'x4-native-provision-123-qualification-' + c['source_revision'], archive_bound)
    artifact_pin(r['admission_inputs_artifact'],
                 'x4-native-provision-123-admission-inputs-' + r['source_revision'], archive_bound)
    all_pins = [*c['artifacts'].values(), r['producer_qualification_artifact'], r['admission_inputs_artifact']]
    require(len({p['id'] for p in all_pins}) == 5, 'Split recovery artifact IDs must be distinct')


def verify_artifact(pin, rows, run, job, expected):
    matches = [x for x in rows if x['id'] == pin['id']]
    require(len(matches) == 1, 'Split recovery artifact missing or duplicated')
    row = matches[0]
    require(row['name'] == pin['name'] and row['size_in_bytes'] == pin['bytes'] and
            row.get('digest') == 'sha256:' + pin['sha256'] and row['expired'] is False and
            row['workflow_run']['id'] == expected['id'] and
            row['workflow_run']['head_sha'] == run['head_sha'] and
            row['workflow_run']['head_branch'] == expected['head_branch'] and
            row['workflow_run']['repository_id'] == row['workflow_run']['head_repository_id'] == run['repository']['id'],
            'Split recovery artifact source/custody differs')
    start, created, end = (datetime.fromisoformat(x.replace('Z', '+00:00')) for x in
                          (job['started_at'], row['created_at'], job['completed_at']))
    require(all(x.tzinfo is not None for x in (start, created, end)) and start <= created <= end,
            'Split recovery artifact belongs to a different attempt')


def verify_run(run, jobs, commit, workflow, expected, source, tree, job_name, conclusion):
    require(run['id'] == expected['id'] and run['run_attempt'] == expected['attempt'] and
            run['workflow_id'] == expected['workflow_id'] and run['path'] == expected['workflow_path'] and
            run['head_sha'] == source and run['head_branch'] == expected['head_branch'] and
            run['event'] == expected['event'] and run['status'] == 'completed' and
            run['conclusion'] == conclusion, 'Split recovery exact run state differs')
    require(run['repository']['full_name'] == run['head_repository']['full_name'] == REPOSITORY and
            run['repository']['id'] == run['head_repository']['id'] == 1408146704, 'Split recovery repository differs')
    if expected['event'] == 'pull_request':
        prs = run['pull_requests']
        require(len(prs) == 1 and prs[0]['number'] == expected['pull_request'] and
                hex_value(prs[0]['head']['sha'], 40) and prs[0]['head']['ref'] == expected['head_branch'] and
                prs[0]['head']['repo']['id'] == prs[0]['base']['repo']['id'] == run['repository']['id'],
                'Original producer PR identity differs')
    require(commit['sha'] == source and commit['commit']['tree']['sha'] == tree and
            sha(workflow) == expected['workflow_sha256'], 'Split recovery source/workflow differs')
    require(len(jobs) == 1 and jobs[0]['id'] == expected['job_id'] and jobs[0]['name'] == job_name and
            jobs[0]['run_id'] == expected['id'] and jobs[0]['run_attempt'] == expected['attempt'] and jobs[0]['head_sha'] == source and
            jobs[0]['status'] == 'completed' and jobs[0]['conclusion'] == conclusion,
            'Split recovery exact job differs')
    return jobs[0]


def verify_original(c, run, jobs, artifacts, commit, workflow, original_steps):
    job = verify_run(run, jobs, commit, workflow, c['run'], c['source_revision'], c['source_tree'], 'qualify', 'failure')
    failed = 'Fresh .123 packages and native build with complete qualification'
    skipped = 'Native artifact and workspace checks'
    for name in ('Clone exact independent clean source roots',
                 'Download and audit the immutable .122 factory and matching complete SD', *original_steps):
        rows = [s for s in job['steps'] if s['name'] == name]
        required = 'failure' if name == failed else 'skipped' if name == skipped else 'success'
        require(len(rows) == 1 and rows[0]['status'] == 'completed' and rows[0]['conclusion'] == required,
                'Original producer step state differs: ' + name)
    require([s['name'] for s in job['steps'] if s['conclusion'] == 'failure'] == [failed],
            'Original producer has another failure')
    require(len(artifacts) == 2, 'Original failed producer artifact set differs')
    for pin in (c['artifacts']['reproducibility'], c['qualification_recovery']['producer_qualification_artifact']):
        verify_artifact(pin, artifacts, run, job, c['run'])


def official_inputs(api, c, source_file, encoded):
    r, prefix = c['qualification_recovery'], 'repos/' + REPOSITORY
    expected = r['run']
    attempt = prefix + '/actions/runs/%d/attempts/%d' % (expected['id'], expected['attempt'])
    run = api.json(attempt)
    jobs = api.pages(attempt + '/jobs', 'jobs')
    artifacts = api.pages(prefix + '/actions/runs/%d/artifacts' % expected['id'], 'artifacts')
    commit = api.json(prefix + '/commits/' + r['source_revision'])
    workflow = source_file(api, r['source_revision'], WORKFLOW)
    job = verify_run(run, jobs, commit, workflow, expected, r['source_revision'], r['source_tree'], 'requalify', 'success')
    for name in STEPS:
        matches = [s for s in job['steps'] if s['name'] == name]
        require(len(matches) == 1 and matches[0]['status'] == 'completed' and matches[0]['conclusion'] == 'success',
                'Required recovery step did not pass: ' + name)
    require(len(artifacts) == 3, 'Recovery artifact set differs')
    for pin in (c['artifacts']['candidate'], c['artifacts']['qualification'], r['admission_inputs_artifact']):
        verify_artifact(pin, artifacts, run, job, expected)
    delta = official_delta(api, c, source_file)
    return {'qualification-source-delta.json': encoded(delta),
            'qualification-ci-run.json': encoded(run), 'qualification-ci-jobs.json': encoded(jobs),
            'qualification-ci-artifacts.json': encoded(artifacts), 'qualification-source-commit.json': encoded(commit)}


def inventory_digest(rows):
    """Match check_runtime_store_admission.store_digest without loading helpers."""
    require(isinstance(rows, dict) and rows and all(valid_record(v) for v in rows.values()),
            'Invalid store digest inventory')
    entries = [{'path': name, 'size_bytes': row['bytes'], 'sha256': row['sha256']}
               for name, row in sorted(rows.items())]
    return sha(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode())


def admission_digests(files, baseline, decode):
    store = {name[len('store/'):]: raw for name, raw in files.items() if name.startswith('store/')}
    rows = {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in store.items()}
    active = {name: {key: row[key] for key in ('bytes', 'sha256')} for name, row in baseline['files'].items()}
    # Reconstruct only the disposable authority control, without changing any
    # delivery byte: it removes exactly Home's new namespace-6 grant.
    boot = decode(store['boot.json'])
    homes = [row for row in boot['app_capabilities'] if row['manifest'] == 'default.json']
    grant = {'capability': 'storage.key-value', 'api': 1, 'instance_id': 6}
    require(len(homes) == 1 and homes[0]['grants'].count(grant) == 1,
            'Factory-only namespace grant missing or duplicated')
    homes[0]['grants'].remove(grant)
    control_boot = (json.dumps(boot, sort_keys=True, indent=2) + '\n').encode()
    control = dict(rows, **{'boot.json': {'bytes': len(control_boot), 'sha256': sha(control_boot)}})
    return inventory_digest(rows), inventory_digest(active), inventory_digest(control)


def verify_candidate(c, files, evidence, q, lock, decode):
    r = c['qualification_recovery']
    for name in EXTRA_FILES:
        require(files[name] == evidence['candidate/' + name], 'Split recovery receipt bytes differ: ' + name)
    custody = decode(files['archive-recovery.json'])
    require(sha(files['archive-recovery.json']) == r['custody_receipt_sha256'] and
            q['qualification_recovery'] == custody and custody['schema'] == 1 and custody['mode'] == MODE,
            'Later-process custody receipt differs')
    for name in ('fresh_build', 'same_process_qualification', 'native_rebuilt', 'packages_rebuilt', 'hardware_tested', 'target_instructions_executed'):
        require(custody[name] is False, 'Recovery must not claim fresh build, rebuild or hardware execution')
    require(custody['producer_source'] == lock['sources']['product'] and
            custody['qualifier']['source']['revision'] == r['source_revision'] and
            custody['qualifier']['source']['tree'] == r['source_tree'] and
            isinstance(custody['qualifier']['source']['submodules'], list), 'Recovery source identities differ')
    require(custody['qualification_run'] == {'repository': REPOSITORY, 'run_id': r['run']['id'],
                                           'attempt': r['run']['attempt'], 'source': r['source_revision']},
            'Recovery receipt run differs')
    require(sha(files['archive-contract.json']) == r['archive_contract_sha256'] == custody['archive_contract_sha256'] and
            decode(files['archive-contract.json']) == custody['archive_contract'], 'Original archive contract differs')
    require(custody['original_source_lock_sha256'] == sha(files['source-lock.json']) and
            custody['original_build_closure_sha256'] == sha(files['original-build-closure.json']) and
            custody['original_package_receipt_sha256'] == sha(files['original-package-build-receipt.json']) and
            decode(files['original-build-closure.json']) == q['build_closure'] and
            decode(files['original-package-build-receipt.json']) == lock['package_build'],
            'Original compiled proof receipts differ')
    archive = custody['archive_contract']
    original = c['run']
    require(archive['schema'] == 1 and archive['qualification_enabled'] is True and
            archive['repository'] == REPOSITORY and archive['source_revision'] == c['source_revision'] and
            archive['source_tree'] == c['source_tree'] and
            archive['original_root'] == '/__w/_temp/x4-provision-123-' + c['source_revision'] and
            archive['artifact'] == c['artifacts']['reproducibility'] and
            archive['run'] == {k: original[k] for k in ('id', 'attempt', 'job_id', 'workflow_id',
                                                       'event', 'pull_request', 'head_branch')} |
            {'workflow': original['workflow_path'], 'workflow_sha256': original['workflow_sha256'],
             'repository_id': 1408146704, 'conclusion': 'failure'},
            'Archive contract does not bind exact original producer')
    changed = custody['qualifier']['changed_files']
    require(isinstance(changed, dict) and changed and set(changed) <= ALLOWED_FILES and all(
        isinstance(v, dict) and set(v) == {'mode', 'producer', 'qualifier'} and
        v['mode'] in ('100644', '100755') and valid_record(v['qualifier']) and
        (v['producer'] is None or valid_record(v['producer'])) for v in changed.values()), 'Qualifier source delta missing')
    restored = custody['restored_files']
    require(isinstance(restored, dict) and restored, 'Restored compiled file closure missing')
    for key, pin in lock['native_files'].items():
        path = 'build/' + pin['path']
        require(restored.get(path) == {k: pin[k] for k in ('bytes', 'sha256')},
                'Restored native file identity differs: ' + key)
    for path, name in ORIGINAL_RECEIPTS.items():
        require(restored.get(path) == {'bytes': len(files[name]), 'sha256': sha(files[name])},
                'Restored original receipt identity differs: ' + path)
    candidate_digest, baseline_digest, control_digest = admission_digests(files, q['baseline_contract'], decode)
    native_elf_digest = lock['native_files']['firmware_elf']['sha256']
    for key in ('admission', 'admission_sanitized'):
        row = q[key]
        require(row['mode'] == 'factory-bootstrap-self-admission' and
                row['active_store_sha256'] == row['candidate_store_sha256'] == candidate_digest, 'Factory self-admission required')
        negative = row['preserving_transition']
        require(negative['expected_rejection'] is True and negative['prepared'] is True and
                negative['cohort_validated'] is False and negative['elf_count'] == 0 and
                negative['active_store_sha256'] == baseline_digest and
                baseline_digest != candidate_digest and
                negative['candidate_store_sha256'] == candidate_digest and
                negative['native_elf_sha256'] == native_elf_digest and
                negative['target_instructions_executed'] is False and
                negative['reason'] == 'Existing paper_clock gains already-owned storage.key-value namespace 6 without migration authority.' and
                negative['runtime_guard'] == 'src/bootstrap/CohortRuntime.inc: used && !owned; !migrating' and
                negative['hardware_calls'] == negative['storage_calls'] == 0 and
                negative['control_packaged'] is False and
                negative['authority_only_control']['elf_count'] == 43 and
                negative['authority_only_control']['cohort_validated'] is True and
                negative['authority_only_control']['prepared'] is True and
                negative['authority_only_control']['hardware_calls'] == negative['authority_only_control']['storage_calls'] == 0 and
                negative['authority_only_control']['active_store_sha256'] == baseline_digest and
                negative['authority_only_control']['candidate_store_sha256'] == control_digest and
                control_digest != candidate_digest and
                negative['authority_only_control']['native_elf_sha256'] == native_elf_digest and
                negative['authority_only_control']['target_instructions_executed'] is False,
                'Unsupported preserving transition negative control missing')

    model = q['preservation_software_model']
    require(model['scope'] == 'byte-range-and-fault-order-only' and
            model['preserving_transition_eligible'] is False and model['namespace_authority_tested'] is False,
            'Offline byte-range model must not claim preserving namespace eligibility')


def valid_record(value):
    return isinstance(value, dict) and set(value) == {'bytes', 'sha256'} and type(value['bytes']) is int and value['bytes'] >= 0 and hex_value(value['sha256'])


def official_delta(api, c, source_file):
    def tree(revision):
        result = api.json('repos/' + REPOSITORY + '/git/trees/' + revision + '?recursive=1')
        require(result['sha'] == revision and result['truncated'] is False, 'Incomplete source tree')
        rows = result['tree']
        require(len(rows) == len({v['path'] for v in rows}), 'Duplicate source tree entry')
        return {v['path']: v for v in rows if v['type'] != 'tree'}
    before, after = tree(c['source_tree']), tree(c['qualification_recovery']['source_tree'])
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    require(changed and changed <= ALLOWED_FILES, 'Official qualifier tree changes compiled inputs')
    result = {}
    for name in sorted(changed):
        new, old = after.get(name), before.get(name)
        require(new and new['type'] == 'blob' and new['mode'] in ('100644', '100755') and
                (old is None or old['type'] == 'blob'), 'Qualifier file deleted or changed type')
        def record_at(pin, revision):
            if pin is None:
                return None
            raw = source_file(api, revision, name)
            require(hashlib.sha1(('blob %d\0' % len(raw)).encode() + raw).hexdigest() == pin['sha'],
                    'Official source blob differs')
            return {'bytes': len(raw), 'sha256': sha(raw)}
        result[name] = {'mode': new['mode'], 'producer': record_at(old, c['source_revision']),
                        'qualifier': record_at(new, c['qualification_recovery']['source_revision'])}
    return result


def verify_source_delta(files, metadata, decode):
    require(decode(files['archive-recovery.json'])['qualifier']['changed_files'] ==
            decode(metadata['qualification-source-delta.json']), 'Custody qualifier delta differs from official source trees')
