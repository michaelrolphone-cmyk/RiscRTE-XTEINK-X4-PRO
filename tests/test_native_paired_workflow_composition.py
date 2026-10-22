import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class WorkflowComposition(unittest.TestCase):
    def test_original_recipe_hash_preserved(self):
        lock=json.loads((ROOT/'docs/native-update-procedure/inputs.json').read_text())
        path='.github/workflows/native-paired-124.yml'
        self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),lock['product']['files'][path])
    def test_full_job_body_preserved(self):
        original=(ROOT/'.github/workflows/native-paired-124.yml').read_text().split('permissions:',1)[1]
        wrapper=(ROOT/'.github/workflows/native-paired-consolidation.yml').read_text().split('permissions:',1)[1]
        wrapper=wrapper.replace('/native-paired-consolidation.yml','/native-paired-124.yml')
        self.assertEqual(wrapper,original)
    def test_wrapper_records_actual_workflow(self):
        text=(ROOT/'.github/workflows/native-paired-consolidation.yml').read_text()
        self.assertIn('  pull_request:',text)
        self.assertNotIn('  push:',text)
        self.assertIn('cp "$NATIVE_ROOT/sources/product/.github/workflows/native-paired-consolidation.yml"',text)

if __name__=='__main__':unittest.main()
