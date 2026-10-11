#!/usr/bin/env python3
"""Check the paired Reader recipe without loading hardware/build dependencies."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pins = json.loads((ROOT / 'minimal/reader-nova7-076-sources.json').read_text())
product = json.loads((ROOT / 'minimal/product.json').read_text())
prior = json.loads((ROOT / 'minimal/reader-static-075-qualification.json').read_text())
source = ast.parse((ROOT / pins['recipe']).read_text())
assignments = {n.targets[0].id: ast.literal_eval(n.value)
               for n in source.body if isinstance(n, ast.Assign)
               and isinstance(n.targets[0], ast.Name)
               and n.targets[0].id in ('BUILDS', 'NATIVE_ELF_SHA')}
assert pins['product_version'] == '0.1.76'
assert product['version'] in ('0.1.76', '0.1.77', '0.1.78', '0.1.79')
assert assignments['BUILDS']['0.1.76'] == (
    prior['image']['sha256'], pins['sources']['system']['version'],
    pins['sources']['productivity']['version'])
assert pins['baseline']['image_sha256'] == prior['image']['sha256']
assert pins['panel_sha256'] == prior['panel_sha256']
assert pins['panel_version'] == prior['panel_version'] == '0.1.12'
assert pins['native_elf_sha256'] == assignments['NATIVE_ELF_SHA'] == prior['native_elf_sha256']
assert pins['reader_sd_path'] == prior['reader']['sd_path']
for entry in pins['sources'].values():
    assert len(entry['commit']) == 40 and all(c in '0123456789abcdef' for c in entry['commit'])
assert '0.1.74' in assignments['BUILDS'] and '0.1.75' in assignments['BUILDS']
assert 'not assembled or hardware tested' in pins['status']
print('NOVA-7 recipe: paired versions, exact source pins, latest baseline and unchanged native/panel PASS')
