"""Cuenta copias exactas entre train, val y test en el ZIP de IP102."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    hashes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    counts: Counter[str] = Counter()
    with zipfile.ZipFile(args.dataset) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            parts = info.filename.replace("\\", "/").split("/")
            split = next((part for part in parts if part in {"train", "val", "test"}), None)
            if split is None:
                continue
            digest = hashlib.sha256(archive.read(info)).hexdigest()
            hashes[digest].append((split, info.filename))
            counts[split] += 1

    duplicates = []
    cross_split = []
    for digest, entries in hashes.items():
        if len(entries) < 2:
            continue
        summary = {"sha256": digest, "splits": sorted({split for split, _ in entries}),
                   "files": [name for _, name in entries]}
        duplicates.append(summary)
        if len(summary["splits"]) > 1:
            cross_split.append(summary)
    report = {"counts": dict(counts), "exact_duplicate_groups": len(duplicates),
              "cross_split_duplicate_groups": len(cross_split),
              "cross_split_examples": cross_split[:20]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
