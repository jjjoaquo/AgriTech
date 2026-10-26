"""Crea un paquete pequeno de produccion, sin datos ni entrenamiento."""

from __future__ import annotations

import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "esparragos-mvp-produccion.tar.gz"
FILES = [
    "app.py", "general_classifier.py", "senasa.py", "requirements.txt",
    "models/classes_ip102.txt",
    "models/esparragos_yolov8n_v2.pt",
    "models/esparragos_yolo26n_semisupervisado.pt",
    "training_runs/yolo26n_semisupervised_v3/external_holdout_comparison.json",
]
OPTIONAL_FILES = ["models/best_resnet152_baseline.safetensors"]


def main() -> None:
    with tarfile.open(OUTPUT, "w:gz") as archive:
        for relative in FILES:
            source = ROOT / relative
            if not source.is_file():
                raise FileNotFoundError(source)
            archive.add(source, arcname=relative)
        for relative in OPTIONAL_FILES:
            source = ROOT / relative
            if source.is_file():
                archive.add(source, arcname=relative)
        for directory in ("templates", "static"):
            for source in (ROOT / directory).rglob("*"):
                if source.is_file():
                    archive.add(source, arcname=source.relative_to(ROOT))
    print(OUTPUT, OUTPUT.stat().st_size)


if __name__ == "__main__":
    main()
