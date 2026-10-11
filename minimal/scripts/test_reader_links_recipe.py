#!/usr/bin/env python3
"""Check that linked Reader assembly selects its paired published components."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pins = json.loads((ROOT / 'minimal/reader-links-077-sources.json').read_text())
product = json.loads((ROOT / 'minimal/product.json').read_text())
spec = importlib.util.spec_from_file_location('reader_overlay', ROOT / pins['recipe'])
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)
assert product['version'] in ('0.1.77', '0.1.78', '0.1.79', '0.1.80', '0.1.81', '0.1.82', '0.1.83', '0.1.84', '0.1.85', '0.1.86', '0.1.87', '0.1.88', '0.1.89', '0.1.90')
assert pins['product_version'] == pins['recipe_version_argument'] == '0.1.77'
selected = recipe.BUILD_SELECTIONS['0.1.77']
assert selected['baseline_version'] == pins['baseline']['version'] == '0.1.76'
assert selected['baseline_sha256'] == pins['baseline']['sha256']
for name in ('reader', 'scene'):
    assert selected[name + '_version'] == pins[name]['version']
    assert selected[name + '_sha256'] == pins[name]['elf_sha256']
    assert len(pins[name]['commit']) == len(pins[name]['tree']) == 40
assert pins['native']['firmware_sha256'] == recipe.NATIVE_SHA
assert pins['native']['tree'] == recipe.RUNTIME_TREE
assert pins['native']['unchanged'] and pins['panel']['unchanged']
assert pins['panel']['elf_sha256'] == recipe.PANEL_SHA
assert pins['panel']['version'] == '0.1.12'
assert pins['reader']['sd_path'] == 'Apps/ebook-reader/ebook_reader.elf'
assert pins['scene']['internal_path'] == 'ui-scene/driver.elf'
# No new capability authority, panel selection, or native recompile is needed.
assert recipe.ALLOWED == {'ui-scene/driver.elf', 'ui-scene/manifest.json', 'ebook_reader.json', 'cohort.json'}
assert recipe.BUILD_SELECTIONS['0.1.76']['baseline_sha256'] == recipe.BASE_SHA
assert recipe.BUILD_SELECTIONS['0.1.76']['reader_version'] == '0.1.6'
print('Reader links recipe: exact 0.1.76 baseline, Reader 0.1.8 + scene 0.3.6, native/panel preservation PASS')
