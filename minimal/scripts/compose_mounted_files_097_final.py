#!/usr/bin/env python3
"""Compose X4 .97 from Files rebuilt at the exact published System source.

The earlier blocked preflight remains reproducible and unchanged. This final
recipe requires verified product publication input for distributable naming.
"""
import argparse
import copy
import json
import tempfile
from pathlib import Path
from compose_mounted_files_097 import (BASE, VERSION, ALLOWED, FILES_NAMES, BANK_STATE,
    BOOTFS, baseline, validate_files, payload, verify_payload, clean_source, read_tree,
    encoded, git, inventory, load_assembly_tools, require, sha, write_files,
    audit_selected_images, verify_image, ordered_build)

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / 'minimal/files-mounted-097-final-inputs.json'
IMAGE = 'X4-0.1.97-FULL-INITIAL-ERASES-DATA.bin'
PREFLIGHT_IMAGE = 'X4-0.1.97-PUBLISHED-SYSTEM-LOCAL-PREFLIGHT.bin'
SYSTEM = '0accd8905b5a64bf5e9269fe92a6e47c9fd1cc90'
SYSTEM_TREE = 'eb8ddcc0c17c915d409593d54b3304a4ca90f87b'


def load_lock():
    lock = json.loads(LOCK_PATH.read_bytes())
    require(lock['product_version'] == VERSION and lock['product_base'] == BASE and
            lock['local_preflight_only'] is False and lock['publication_blocked'] is False and
            lock['published_system_commit'] == lock['system_build_commit'] ==
            lock['system_qualification_commit'] == SYSTEM and
            lock['system_build_tree'] == lock['system_qualification_tree'] == SYSTEM_TREE and
            lock['rebuild_from_final_published_system_required'] is False,
            'Final Files source lock does not bind the published System rebuild')
    require(lock['system_publication']['commit'] == SYSTEM and
            lock['system_publication']['tree'] == SYSTEM_TREE and
            lock['qualified_preflight']['elf_and_manifest_byte_identical'] is True,
            'System publication/rebuild proof differs')
    return lock


def publication(path, revision, tree, preflight):
    if preflight:
        require(path is None, 'Preflight must not claim product publication')
        return None
    require(path is not None, 'Final output requires a verified product publication receipt')
    proof = json.loads(path.read_bytes())
    require(proof['repository'] == 'michaelrolphone-cmyk/RiskRTE-XTEINK-X4-PRO' and
            proof['commit'] == revision and proof['tree'] == tree and
            proof['branch'] == 'feat/x4-mounted-files-097-20261012' and
            proof['readback_verified'] is True and proof['readback_verified_at'],
            'Product publication does not match this exact clean source')
    return proof


def compose(a):
    require(not a.output.exists(), 'Output must be new')
    lock = load_lock()
    clean_source(ROOT, a.product_revision, 'Product')
    tree = git(ROOT, 'rev-parse', 'HEAD^{tree}')
    proof = publication(a.product_publication, a.product_revision, tree, a.preflight_only)
    require(git(ROOT, 'merge-base', BASE, a.product_revision) == BASE, 'Product must descend from .96')
    clean_source(a.runtime_source, lock['runtime_commit'], 'Runtime')
    require(git(a.runtime_source, 'rev-parse', 'HEAD^{tree}') == lock['runtime_tree'], 'Wrong Runtime tree')
    clean_source(a.system_source, SYSTEM, 'Published System')
    require(git(a.system_source, 'rev-parse', 'HEAD^{tree}') == SYSTEM_TREE, 'Wrong published System tree')
    base, old, sd, parts, full = baseline(a.baseline, lock)
    artifacts = {n: (a.files / n).read_bytes() for n in FILES_NAMES}
    validate_files(artifacts, a.system_source, old, lock)
    new = payload(old, sd, artifacts, a.product_revision, base['sd_lifecycle'])
    build, read_image, initial, parse = load_assembly_tools(a.tools, a.runtime_source)
    image, packing = ordered_build(new, build)
    state = initial(parts['firmware.bin'], image, True)
    result = bytearray(full)
    result[slice(*BOOTFS)], result[slice(*BANK_STATE)] = image, state
    verify_image(bytes(result), full, old, new, read_image, parse, parts['firmware.bin'])
    with tempfile.TemporaryDirectory(prefix='x4-097-final-selected-') as tmp:
        root = Path(tmp)
        write_files(root / 'store', new)
        write_files(root / 'SD', sd)
        selected = audit_selected_images(json.loads(new['boot.json']), root / 'store', root / 'SD')
    require(selected == base['selected_sd_images'] and len(selected) == 46, 'Selected SD executables changed')
    parts = dict(parts, **{'bootfs.bin': image, 'bank_state.bin': state})
    receipt = copy.deepcopy(base)
    receipt.pop('files_1_5_30_unchanged', None)
    receipt.pop('sd_overlay', None)
    receipt.update(product_version=VERSION, product_source=a.product_revision, product_tree=tree,
        product_base=BASE, baseline_full_image_sha256=lock['baseline_full_image_sha256'],
        baseline_receipt_sha256=lock['baseline_receipts']['receipts/sd-lifecycle-composition.json'],
        baseline_receipts=lock['baseline_receipts'], local_preflight_only=a.preflight_only,
        publication_ready=not a.preflight_only, final_published_system_source_pending=False,
        final_rebuild_required=False, product_published=not a.preflight_only, system_published=True,
        system_commit=SYSTEM, system_tree=SYSTEM_TREE, system_qualification_commit=SYSTEM,
        source_publication=dict(system=lock['system_publication'], product=proof),
        native_rebuilt=False, native_unchanged=True, home_rebuilt=False,
        packaging_only_changes=False, files_replaced=True,
        files_client=dict(version=lock['files_version'], system_commit=SYSTEM,
                          artifacts=inventory(artifacts), grants=16, source_file_count=312),
        recipe_sha256=sha(Path(__file__).read_bytes()), files_lock_sha256=sha(LOCK_PATH.read_bytes()),
        store=inventory(new), sd=inventory(sd), packing_sha256=sha(encoded(packing)),
        changed_store_paths=sorted(ALLOWED), changed_sd_paths=[],
        sd_overlay_required=False, sd_deliverable_created=False,
        sd_baseline_requires_delivered_096_overlay=True, baseline_sd_overlay=lock['baseline_overlay'],
        original_sd_files_preserved=81, all_sd_executables_preserved=True, preserved_store_files=100,
        components={n: dict(bytes=len(v), sha256=sha(v), offset=base['components'][n]['offset']) for n,v in parts.items()},
        full_image_bytes=len(result), full_image_sha256=sha(result), hardware_tested=False)
    a.output.mkdir(parents=True)
    write_files(a.output / 'store', new)
    write_files(a.output / 'SD', sd)
    write_files(a.output / 'components', parts)
    write_files(a.output / 'receipts/files-client', artifacts)
    write_files(a.output / 'receipts', {'mounted-files-composition.json': encoded(receipt),
        'packing.json': encoded(packing), 'baseline-sd-lifecycle-composition.json': encoded(base)})
    path = a.output / (PREFLIGHT_IMAGE if a.preflight_only else IMAGE)
    path.write_bytes(result)
    require(path.read_bytes() == result and read_tree(a.output / 'store') == new and
            read_tree(a.output / 'SD') == sd, 'Written image/store/SD mismatch')
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('baseline', 'files', 'system-source', 'runtime-source', 'tools', 'output'):
        p.add_argument('--' + n, type=Path, required=True)
    p.add_argument('--product-revision', required=True)
    p.add_argument('--product-publication', type=Path)
    p.add_argument('--preflight-only', action='store_true')
    print(json.dumps(compose(p.parse_args()), indent=2))
