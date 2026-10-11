#!/usr/bin/env python3
"""Selected-board dependency and publication boundaries for SD placement."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('placement', Path(__file__).parents[1] / 'scripts/prepare_sd_first.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def cap(name):
    return {'capability': name, 'api': 1}


class Placement(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.output = self.root / 'output'
        self.boot = {'board': 'board.json', 'installation': {'volume_instance': 9},
                     'drivers': [{'manifest': f'{name}/manifest.json', 'instance_id': instance}
                                 for name, instance in [('power', 1), ('sd', 9), ('render', 3), ('app-service', 0)]]}
        self.board = {'devices': [{'instance_id': 9, 'bindings': {'board.power': 1}},
                                  {'instance_id': 0, 'bindings': {'display.output': 3}}]}
        self.manifests = {}
        for name, offer, needs in [('power', 'board.power', ['platform.gpio']),
                                   ('sd', 'storage.volume', ['board.power']),
                                   ('render', 'display.output', []),
                                   ('app-service', 'app.service', ['display.output'])]:
            self.manifests[name] = {'id': name, 'type': 'driver', 'version': '1.0.0',
                                    'file_name': 'driver.elf', 'provides': [cap(offer)],
                                    'requires': [cap(n) for n in needs]}
            (self.source / name).mkdir()
            (self.source / name / 'driver.elf').write_bytes(b'fixture-'+name.encode())

    def write(self):
        (self.source / 'boot.json').write_text(json.dumps(self.boot))
        (self.source / 'board.json').write_text(json.dumps(self.board))
        for name, manifest in self.manifests.items():
            (self.source / name / 'manifest.json').write_text(json.dumps(manifest))

    def reject(self, message):
        self.write()
        with self.assertRaisesRegex(ValueError, message):
            module.prepare(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_mount_closure_and_metadata_preserved(self):
        self.write()
        original = (self.source / 'boot.json').read_bytes()
        receipt = module.prepare(self.source, self.output)
        self.assertEqual(receipt['bootstrap_internal'], ['power', 'sd'])
        rows = json.loads((self.output / 'store/boot.json').read_text())['drivers']
        for index in [0, 1]: self.assertNotIn('image_source', rows[index])
        for index in [2, 3]:
            selected = rows[index]['image_source']
            self.assertTrue(selected['internal_fallback'])
            self.assertEqual(selected['volume_instance'], 9)
            self.assertTrue((self.output / 'sd' / selected['path']).is_file())
        self.assertEqual(original, (self.source / 'boot.json').read_bytes())
        for path in self.source.rglob('driver.elf'):
            self.assertEqual(path.read_bytes(), (self.output / 'store' / path.relative_to(self.source)).read_bytes())

    def test_explicit_internal_pins_transitive_dependencies(self):
        self.write()
        r = module.prepare(self.source, self.output, ['app-service'])
        self.assertEqual(set(r['bootstrap_internal']), set(self.manifests))
        self.assertFalse((self.output / 'sd').exists())

    def test_cycle_rejects_before_publication(self):
        self.manifests['power']['requires'] = [cap('storage.volume')]
        self.reject('dependency cycle')

    def test_wrong_board_binding_rejects(self):
        self.board['devices'][0]['bindings']['board.power'] = 44
        self.reject('no exact selected binding')

    def test_ambiguous_provider_rejects(self):
        self.boot['drivers'].append({'manifest': 'render/manifest.json', 'instance_id': 4})
        self.board['devices'][1]['bindings'] = {}
        self.reject('no exact selected binding')

    def test_exact_board_binding_resolves_ambiguity(self):
        self.boot['drivers'].append({'manifest': 'render/manifest.json', 'instance_id': 4})
        self.write()
        r = module.prepare(self.source, self.output)
        self.assertEqual(next(p for p in r['packages'] if p['id']=='app-service')['dependencies'], ['render'])

    def test_missing_mount_rejects(self):
        self.boot['installation']['volume_instance'] = 10
        self.reject('one selected installation volume')

    def test_invalid_image_rejects_without_output(self):
        self.manifests['app-service']['file_name'] = '../driver.elf'
        self.reject('invalid image basename')

    def test_missing_image_rejects_without_output(self):
        (self.source / 'render/driver.elf').unlink()
        self.reject('regular selected image')

    def test_symlink_image_rejects_without_output(self):
        image = self.source / 'render/driver.elf'
        image.unlink(); image.symlink_to(self.source / 'power/driver.elf')
        self.reject('regular selected image')

    def test_existing_output_rejects(self):
        self.write(); self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'new output'):
            module.prepare(self.source, self.output)


if __name__ == '__main__': unittest.main()
