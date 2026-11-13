"""Build a reviewable UI archive, never a production model bundle."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MVP = ROOT / "mvp"
OUT = MVP / "test-results"


def main() -> None:
    files = sorted(
        (path for directory in ("templates", "static") for path in (MVP / directory).rglob("*") if path.is_file()),
        key=lambda path: str(path.relative_to(MVP)),
    )
    if not files:
        raise SystemExit("No hay archivos de interfaz para empaquetar")
    OUT.mkdir(exist_ok=True)
    manifest = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "purpose": "Evidencia revisable de la interfaz; no es un despliegue ni incluye modelos",
        "files": {
            str(path.relative_to(MVP)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }
    manifest_path = OUT / "interfaz-agritech-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_path = OUT / "interfaz-agritech.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=str(path.relative_to(MVP)).replace("\\", "/"))
        archive.write(manifest_path, arcname="manifest.json")
    with zipfile.ZipFile(archive_path) as archive:
        for name, digest in manifest["files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise SystemExit(f"SHA256 incorrecto: {name}")
    print(f"Paquete: {archive_path}; {len(files)} archivos verificados")


if __name__ == "__main__":
    main()
