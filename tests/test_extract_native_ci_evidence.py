#!/usr/bin/env python3
import copy
import importlib.util
import json
import stat
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("extract", ROOT / "scripts/extract_native_ci_evidence.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


class Controls(unittest.TestCase):
    def test_metadata_identity(self):
        meta = {"id": extract.ARTIFACT, "size_in_bytes": extract.ARCHIVE_BYTES,
                "digest": "sha256:" + extract.ARCHIVE_SHA, "expired": False,
                "name": "x4-native-provision-123-reproducibility-" + extract.SOURCE,
                "workflow_run": {"id": extract.RUN, "head_sha": extract.SOURCE}}
        extract.verify_metadata(meta)
        for key in ("id", "size_in_bytes", "digest", "expired", "name", "workflow_run"):
            bad = copy.deepcopy(meta)
            bad[key] = {"id": 0, "head_sha": "0" * 40} if key == "workflow_run" else True if key == "expired" else "invalid"
            with self.subTest(key=key), self.assertRaises(ValueError):
                extract.verify_metadata(bad)

    def run_archive(self, extra=(), missing=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        archive = root / "input.zip"
        with warnings.catch_warnings(), ZipFile(archive, "w") as zipped:
            warnings.simplefilter("ignore", UserWarning)
            for name in sorted(extract.REQUIRED if not missing else {"build/riscrte_native.map"}):
                zipped.writestr(name, b"exact bytes")
            for name, content in extra:
                zipped.writestr(name, content)
        return archive, root / "out"

    def test_selected_only(self):
        archive, out = self.run_archive([("unselected/never-execute", b"ignored")])
        rows = extract.extract_selected(archive, out)
        self.assertEqual({row["path"] for row in rows}, extract.REQUIRED)
        self.assertFalse((out / "unselected").exists())
        self.assertTrue(all(row["bytes"] == 11 for row in rows))
        self.assertTrue(all(row["sha256"] == extract.digest(out / row["path"]) for row in rows))

    def test_bad_paths(self):
        for name in ("../outside", "/absolute", "build/../escape", "build/./file", "build//file", "build\\file"):
            with self.subTest(name=name):
                archive, out = self.run_archive([(name, b"bad")])
                with self.assertRaises(ValueError):
                    extract.extract_selected(archive, out)
                self.assertFalse(out.exists())

    def test_duplicate(self):
        archive, out = self.run_archive([("build/riscrte_native.elf", b"duplicate")])
        with self.assertRaises(ValueError):
            extract.extract_selected(archive, out)

    def test_symlink(self):
        link = ZipInfo("unselected/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive, out = self.run_archive([(link, b"../../outside")])
        with self.assertRaises(ValueError):
            extract.extract_selected(archive, out)

    def test_missing_linked_file(self):
        archive, out = self.run_archive(missing=True)
        with self.assertRaises(ValueError):
            extract.extract_selected(archive, out)

    def test_selected_size_cap(self):
        archive, out = self.run_archive()
        with patch.object(extract, "MAX_SELECTED", 1), self.assertRaises(ValueError):
            extract.extract_selected(archive, out)
        self.assertFalse(out.exists())

    def test_fresh_output_required(self):
        archive, out = self.run_archive()
        out.mkdir()
        with self.assertRaises(ValueError):
            extract.extract_selected(archive, out)


if __name__ == "__main__":
    unittest.main()
