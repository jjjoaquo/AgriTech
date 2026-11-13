"""Block accidentally committed model weights and oversized media files."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 25 * 1024 * 1024


def main() -> None:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    sizes = {}
    for raw in tracked:
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = ROOT / relative
        if path.is_file():
            sizes[relative] = path.stat().st_size
    oversized = {name: size for name, size in sizes.items() if size > LIMIT}
    output = ROOT / "mvp" / "test-results" / "tamano-repositorio.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "limit_bytes": LIMIT,
                "tracked_files": len(sizes),
                "largest": dict(sorted(sizes.items(), key=lambda item: -item[1])[:10]),
                "oversized": oversized,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"{len(sizes)} archivos rastreados; {len(oversized)} superan 25 MiB")
    if oversized:
        raise SystemExit("Hay archivos demasiado grandes para Git: " + ", ".join(oversized))


if __name__ == "__main__":
    main()
