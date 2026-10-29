"""Entrena YOLO26 y compara con V2 en un test independiente de ambos.

NO usar con el Roboflow v1 agrupado: V2 probablemente vio sus originales.
Requiere fotos nuevas con recuadros revisados de las siete clases.
Uso: python train_compare.py C:/ruta/al/data.yaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "models" / "esparragos_yolov8n_v2.pt"


def audit_dataset(data: dict, data_yaml: Path) -> None:
    """Impide comparar con splits vacíos, clases distintas o fotos repetidas."""
    expected = YOLO(str(BASELINE)).names
    names = data["names"]
    names = {int(k): v for k, v in names.items()} if isinstance(names, dict) else dict(enumerate(names))
    if names != expected:
        raise ValueError(f"Las clases y su orden deben coincidir con V2: {expected}")
    root = Path(data.get("path", data_yaml.parent))
    if not root.is_absolute():
        root = (data_yaml.parent / root).resolve()
    seen: dict[str, str] = {}
    import hashlib
    from collections import Counter
    for split in ("train", "val", "test"):
        entry = data[split]
        paths = entry if isinstance(entry, list) else [entry]
        images = []
        for relative in paths:
            source = Path(relative)
            if not source.is_absolute():
                source = root / source
            if source.is_dir():
                images += [p for p in source.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
            elif source.is_file() and source.suffix.lower() == ".txt":
                images += [Path(line.strip()) for line in source.read_text().splitlines() if line.strip()]
            else:
                raise ValueError(f"No se encontró el conjunto {split}: {source}")
        if not images:
            raise ValueError(f"El conjunto {split} está vacío")
        classes = Counter()
        for image in images:
            if not image.is_file():
                raise ValueError(f"Falta imagen: {image}")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            if digest in seen and seen[digest] != split:
                raise ValueError(f"Imagen idéntica en {seen[digest]} y {split}: {image}")
            seen[digest] = split
            label = Path(str(image).replace("\\images\\", "\\labels\\").replace("/images/", "/labels/")).with_suffix(".txt")
            if not label.is_file():
                raise ValueError(f"Falta etiqueta: {label}")
            for line in label.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    raise ValueError(f"Etiqueta YOLO inválida: {label}")
                cid = int(parts[0])
                xywh = [float(v) for v in parts[1:]]
                if cid not in expected or any(not 0 <= v <= 1 for v in xywh) or xywh[2] <= 0 or xywh[3] <= 0:
                    raise ValueError(f"Caja fuera de rango: {label}")
                classes[cid] += 1
        if set(classes) != set(expected):
            raise ValueError(f"El conjunto {split} no cubre las siete clases: {dict(classes)}")
        print(f"{split}: {len(images)} imágenes; cajas por clase {dict(classes)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_yaml", type=Path)
    parser.add_argument("--epochs", type=int, default=75)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()
    data_yaml = args.data_yaml.resolve()
    if not data_yaml.is_file():
        parser.error(f"No existe {data_yaml}")
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not all(k in data for k in ("train", "val", "test", "names")):
        parser.error("data.yaml debe declarar train, val, test y names. Reserva test fuera del entrenamiento.")
    if len(data["names"]) != 7:
        parser.error("Se esperaban las siete clases de plagas del proyecto.")
    audit_dataset(data, data_yaml)
    model = YOLO("yolo26n.pt")
    training = model.train(data=str(data_yaml), epochs=args.epochs, imgsz=args.imgsz,
                           project=str(ROOT / "training_runs"), name="yolo26n_esparragos")
    new_weights = Path(training.save_dir) / "weights" / "best.pt"
    report = {}
    for label, weights in (("yolov8n_v2", BASELINE), ("yolo26n", new_weights)):
        metrics = YOLO(str(weights)).val(data=str(data_yaml), split="test", imgsz=args.imgsz,
                                         project=str(ROOT / "training_runs"), name=f"test_{label}")
        report[label] = {
            "weights": str(weights),
            "precision": float(metrics.box.mp),
            "recall": float(metrics.box.mr),
            "map50": float(metrics.box.map50),
            "map50_95": float(metrics.box.map),
            "inference_ms_per_image": float(metrics.speed["inference"]),
        }
    output = ROOT / "training_runs" / "comparison.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Comparación guardada en {output}")
    print("Prueba también ambos modelos con video de campo antes de reemplazar el modelo del MVP.")


if __name__ == "__main__":
    main()
