#!/usr/bin/env python3
"""Standalone source/recipe guards; does not claim full-image qualification.

Optional --built-files and --system-source additionally verify the independently
rebuilt target component. Full .97 admission needs the delivered .96 BIN/SD tree.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'minimal/scripts'))
import compose_mounted_files_097_final as c

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--built-files', type=Path)
p.add_argument('--system-source', type=Path)
a = p.parse_args()
assert bool(a.built_files) == bool(a.system_source), 'Both target inputs are required together'
lock = c.load_lock()
evidence = ROOT / 'minimal/docs/evidence/mounted-files-097-final'
receipt_raw = (evidence / 'final-composition.json').read_bytes()
assert c.sha(receipt_raw) == '2fe8247a7d9bd45d3ffac80e20ed37de5dd74faea84566e0b14940b071a748ff'
receipt = json.loads(receipt_raw)
assert receipt['product_source'] == 'e9332c3fe731ed63508e223bcd67cedf481462e4'
assert receipt['product_tree'] == 'f2db835c8a7797017f1e7ca526f0aba4ce9e0e85'
assert receipt['full_image_sha256'] == 'd18ad4726d6503b53a17c556cc1e8bc6a40769885c7c60c176b393707a499dd6'
assert receipt['full_image_bytes'] == 16777216
assert receipt['product_base'] == c.BASE and receipt['product_version'] == c.VERSION == '0.1.97'
assert receipt['system_commit'] == c.SYSTEM == lock['published_system_commit']
assert receipt['system_tree'] == c.SYSTEM_TREE
assert receipt['recipe_sha256'] == c.sha(Path(c.__file__).read_bytes())
assert receipt['files_lock_sha256'] == c.sha(c.LOCK_PATH.read_bytes())
assert receipt['files_client']['artifacts'] == lock['files_artifacts']
assert receipt['changed_store_paths'] == sorted(c.ALLOWED)
assert receipt['changed_sd_paths'] == receipt['added_sd_files'] == []
assert receipt['preserved_store_files'] == 100 and receipt['original_sd_files_preserved'] == 81
assert receipt['native_unchanged'] and not receipt['native_rebuilt'] and not receipt['home_rebuilt']
assert receipt['boot_authority_unchanged'] and receipt['sd_baseline_requires_delivered_096_overlay']
assert not receipt['sd_overlay_required'] and not receipt['sd_deliverable_created']
assert receipt['publication_ready'] and receipt['product_published'] and receipt['system_published']
assert not receipt['local_preflight_only'] and not receipt['final_rebuild_required']
assert len(receipt['sd_lifecycle']) == 13 and len(receipt['selected_sd_images']) == 46

record_raw = (evidence / 'file_browser-build-record.json').read_bytes()
record = json.loads(record_raw)
assert c.sha(record_raw) == lock['files_artifacts']['file_browser-build-record.json']
assert c.sha((evidence / 'file_browser.json').read_bytes()) == lock['files_artifacts']['file_browser.json']
assert record['repository_commit'] == c.SYSTEM and record['working_tree_dirty'] is False
assert record['version'] == '1.5.31' and record['sha256'] == lock['files_artifacts']['file_browser.elf']
assert record['grant_count'] == 16 and len(record['source_sha256']) == 312
for key, expected in lock['profile_invariants'].items():
    assert record[key] == expected, 'Profile/grant drift: ' + key

rejected = []
def reject(name, fn):
    try:
        fn()
    except (ValueError, KeyError):
        rejected.append(name)
        return
    raise AssertionError('Accepted invalid publication: ' + name)

reject('missing', lambda: c.publication(None, receipt['product_source'], receipt['product_tree'], False))
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'publication.json'
    proof = receipt['source_publication']['product']
    path.write_bytes(c.encoded(proof))
    assert c.publication(path, receipt['product_source'], receipt['product_tree'], False) == proof
    reject('preflight-claim', lambda: c.publication(path, receipt['product_source'], receipt['product_tree'], True))
    for key, value in (('repository', 'wrong/repository'), ('commit', '0'*40), ('tree', '0'*40),
                       ('branch', 'wrong'), ('readback_verified', False), ('readback_verified_at', '')):
        bad = dict(proof); bad[key] = value; path.write_bytes(c.encoded(bad))
        reject(key, lambda: c.publication(path, receipt['product_source'], receipt['product_tree'], False))

target_verified = False
if a.built_files:
    assert subprocess.check_output(['git', '-C', str(a.system_source), 'rev-parse', 'HEAD'], text=True).strip() == c.SYSTEM
    assert not subprocess.check_output(['git', '-C', str(a.system_source), 'status', '--porcelain'], text=True).strip()
    for name in ('file_browser.elf', 'file_browser.json'):
        assert c.sha((a.built_files / name).read_bytes()) == lock['files_artifacts'][name], name + ' differs'
    built = json.loads((a.built_files / 'file_browser-build-record.json').read_bytes())
    expected = copy.deepcopy(record)
    # This field identifies the build machine's SDK directory, not source bytes.
    expected['resident_shell']['runtime_sdk'] = built['resident_shell']['runtime_sdk']
    assert built == expected, 'Target build receipt differs beyond its machine-local SDK path'
    for name, digest in record['source_sha256'].items():
        assert c.sha((a.system_source / name).read_bytes()) == digest, 'Compiled source drift: ' + name
    target_verified = True

print(json.dumps(dict(passed=True,scope='Standalone recipe/source and optional target-component checks; no full-image/native/provider execution claim',
    product_artifact_source=receipt['product_source'],publication_rejections=len(rejected),
    source_hashes_in_pinned_record=312,files_grants=16,target_component_rebuilt_and_verified=target_verified,
    full_image_admission_run=False,hardware_tested=False),indent=2))
