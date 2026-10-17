#!/usr/bin/env python3
"""Current Runtime source-binding adapter contracts, without hardware access."""
import sys
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_idf61_qualification as qualification

class SourceBoundFixture(unittest.TestCase):
    def test_metadata_and_candidate_image_use_explicit_sources(self):
        source = "#undef private\n  RiscBoot::Runtime runtime(runtimePort);\nRiscBoot::Runtime candidate({});unsigned admitted=0;\nstorageCalls,admitted,cooperativeYields);"
        adapted = qualification.source_bound_fixture(source, Path('/locked/runtime'))
        self.assertIn('/locked/runtime/test/RuntimeFileFixture.h', adapted)
        self.assertIn('runtimePort.files=files.sources();', adapted)
        self.assertIn('std::string(argv[1]),std::string(argv[2])', adapted)
        self.assertIn('CohortElf::Context admitted{&candidate,0}', adapted)
        self.assertIn('admitted.admitted', adapted)
        for altered in (source.replace('#undef private', ''), source + source):
            with self.assertRaises(ValueError):
                qualification.source_bound_fixture(altered, Path('/locked/runtime'))

    def test_image_reader_keeps_production_admission_and_roles(self):
        prefix = '// exact production export table and admitElf implementation\n'
        header = prefix + 'static bool file(void* context,const char* path,bool provider){\n obsolete();\n}\n// suffix\n'
        adapted = qualification.source_bound_header(header)
        self.assertIn(prefix, adapted)
        self.assertTrue(adapted.endswith('// suffix\n'))
        self.assertIn('c.candidate->imageSource()', adapted)
        self.assertIn('admitElf(image.bytes,image.size,provider?ElfRole::Driver:ElfRole::Application)', adapted)
        self.assertIn('operationSafe()', adapted)
        self.assertIn('free(image.bytes);if(!valid)return false;', adapted)
        self.assertNotIn('obsolete()', adapted)
        with self.assertRaises(ValueError):
            qualification.source_bound_header('changed header')

class SourceBoundVersion(unittest.TestCase):
    def test_linked_version_requires_exact_source_and_unique_markers(self):
        import tempfile
        import native_idf61_candidate as recipe
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'platformio.ini').write_text('[common]\nversion = 0.4.7\n')
            good = b'RISC_RUNTIME_VERSION:0.4.7\0'
            blobs = dict(firmware_bin=good, firmware_elf=good)
            recipe.verify_runtime_version(blobs, root)
            for key in blobs:
                for bad in (b'', b'RISC_RUNTIME_VERSION:0.4.0\0', good + good):
                    with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                        recipe.verify_runtime_version({**blobs, key: bad}, root)
            for config in ('', 'version = invalid\n', 'version = 0.4.7\nversion = invalid\n'):
                (root / 'platformio.ini').write_text(config)
                with self.assertRaises(ValueError):
                    recipe.verify_runtime_version(blobs, root)

if __name__ == '__main__':
    unittest.main()
