#!/usr/bin/env python3
"""Read-only extraction of the pinned failed .123 CI link evidence. No rebuild."""
import argparse
import hashlib
import json
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

RUN = 38967581920
SOURCE = "e78a6734688a01b81108e54a172cc124960ff8ce"
ARTIFACT = 12075952814
ARCHIVE_BYTES = 779398722
ARCHIVE_SHA = "80a0489b7b22c4aa48032c0ed4124c4030f4e937bc1e9cbe58f48feab093b1e4"
MAX_SELECTED = 64 * 1024 * 1024
REQUIRED = {"build/riscrte_native.elf", "build/riscrte_native.map"}
SELECTED = REQUIRED | {
    "build/compile_commands.json", "build/project_description.json", "build/sdkconfig",
    "build/config/sdkconfig.h", "build/config/sdkconfig.json",
    "build/toolchain/cflags", "build/toolchain/cxxflags", "build/toolchain/asmflags",
    "build/toolchain/ldflags", "build/toolchain/toolchain-esp32s3.cmake",
    "build/x4-native-idf61/selection.txt", "build/native-build-evidence/source-lock.json",
    "logs/controlled-build.log", "metadata/workflow.yml", "metadata/source-rows.txt",
    "source-evidence/product-identity.txt", "source-evidence/runtime-identity.txt",
    "source-evidence/sdk-identity.txt",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify_metadata(meta):
    require(meta["id"] == ARTIFACT and meta["size_in_bytes"] == ARCHIVE_BYTES,
            "wrong artifact identity or size")
    require(meta["digest"] == "sha256:" + ARCHIVE_SHA and not meta["expired"],
            "wrong artifact digest or expired artifact")
    require(meta["name"] == "x4-native-provision-123-reproducibility-" + SOURCE,
            "wrong artifact name")
    require(meta["workflow_run"]["id"] == RUN and meta["workflow_run"]["head_sha"] == SOURCE,
            "wrong producing run or source")


def extract_selected(archive, output):
    require(not output.exists(), "output must be fresh")
    with ZipFile(archive) as zipped:
        seen = set()
        chosen = []
        for item in zipped.infolist():
            name = item.filename
            path = PurePosixPath(name)
            require(name and not path.is_absolute() and "\\" not in name and
                    all(part not in ("", ".", "..") for part in name.rstrip("/").split("/")),
                    "unsafe archive path")
            require(name not in seen, "duplicate archive path")
            seen.add(name)
            mode = item.external_attr >> 16
            require(not stat.S_ISLNK(mode) and not item.flag_bits & 1,
                    "symlink or encrypted archive entry")
            if name in SELECTED:
                require(not item.is_dir(), "selected file is a directory")
                chosen.append(item)
        require(REQUIRED <= seen, "missing final ELF or map")
        require(sum(item.file_size for item in chosen) <= MAX_SELECTED,
                "selected evidence exceeds bounded size")
        output.mkdir(parents=True)
        rows = []
        for item in chosen:
            target = output / item.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            with zipped.open(item) as source, target.open("xb") as destination:
                while chunk := source.read(1024 * 1024):
                    count += len(chunk)
                    require(count <= item.file_size, "entry exceeds declared size")
                    destination.write(chunk)
            require(count == item.file_size, "entry size mismatch")
            rows.append({"path": item.filename, "bytes": count, "sha256": digest(target)})
        return sorted(rows, key=lambda row: row["path"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    meta = json.loads(args.metadata.read_bytes())
    verify_metadata(meta)
    require(args.archive.stat().st_size == ARCHIVE_BYTES, "archive byte size mismatch")
    require(digest(args.archive) == ARCHIVE_SHA, "archive SHA-256 mismatch")
    rows = extract_selected(args.archive, args.output)
    receipt = {"schema": 1, "run": RUN, "source": SOURCE, "artifact": ARTIFACT,
               "archive_bytes": ARCHIVE_BYTES, "archive_sha256": ARCHIVE_SHA,
               "selected": rows, "scope": "Exact failed CI link evidence only; no rebuild, execution or qualification."}
    (args.output / "extraction-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
