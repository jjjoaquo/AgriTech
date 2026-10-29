"""Entrena YOLO26 para mejorar precisión y compara sin tocar el modelo de producción.

Usa un dataset con train/val/test anotados manualmente y sin imágenes repetidas
entre particiones. El test se reserva exclusivamente para la comparación final.

Ejemplo:
  python train_yolo26_precision.py /ruta/data.yaml --device 0
  python train_yolo26_precision.py /ruta/data.yaml --device cpu --epochs 100
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
BASELINE_DEFAULT = ROOT / "models" / "esparragos_yolov8n_v2.pt"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def normalize_names(names: Any) -> dict[int, str]:
    if isinstance(names, dict):
        return {int(key): str(value) for key, value in names.items()}
    if isinstance(names, list):
        return dict(enumerate(map(str, names)))
    raise ValueError("data.yaml debe definir names como lista o diccionario.")


def resolve_split_images(entry: Any, dataset_root: Path) -> list[Path]:
    entries = entry if isinstance(entry, list) else [entry]
    images: list[Path] = []
    for value in entries:
        source = Path(str(value))
        if not source.is_absolute():
            source = dataset_root / source
        if source.is_dir():
            images.extend(p for p in source.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS)
        elif source.is_file() and source.suffix.lower() == ".txt":
            for line in source.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    image = Path(line)
                    if not image.is_absolute():
                        image = dataset_root / image
                    images.append(image)
        elif source.is_file() and source.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(source)
        else:
            raise ValueError(f"No se encuentra la ruta de datos: {source}")
    return sorted(set(p.resolve() for p in images))


def label_path_for(image: Path) -> Path:
    parts = list(image.parts)
    image_positions = [i for i, part in enumerate(parts) if part.lower() == "images"]
    if not image_positions:
        raise ValueError(
            f"No puedo inferir la ruta de etiquetas de {image}. "
            "Organiza el dataset en carpetas images/ y labels/."
        )
    parts[image_positions[-1]] = "labels"
    return Path(*parts).with_suffix(".txt")


def audit_dataset(data: dict[str, Any], yaml_path: Path) -> dict[str, Any]:
    """Valida etiquetas, cobertura y fugas por imágenes idénticas entre splits."""
    required = {"train", "val", "test", "names"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"Faltan campos obligatorios en data.yaml: {sorted(missing)}")

    names = normalize_names(data["names"])
    if len(names) != 7 or set(names) != set(range(7)):
        raise ValueError("Se esperan exactamente 7 clases con IDs consecutivos 0..6.")

    root_value = Path(str(data.get("path", yaml_path.parent)))
    dataset_root = root_value if root_value.is_absolute() else (yaml_path.parent / root_value)
    dataset_root = dataset_root.resolve()
    seen_hashes: dict[str, str] = {}
    split_summary: dict[str, Any] = {}

    for split in ("train", "val", "test"):
        images = resolve_split_images(data[split], dataset_root)
        if not images:
            raise ValueError(f"La partición {split} está vacía.")
        class_counts: Counter[int] = Counter()
        for image in images:
            if not image.is_file():
                raise ValueError(f"No existe la imagen: {image}")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            previous = seen_hashes.get(digest)
            if previous is not None and previous != split:
                raise ValueError(
                    f"Fuga de datos: la imagen {image} aparece en {previous} y {split}."
                )
            seen_hashes[digest] = split

            label = label_path_for(image)
            if not label.is_file():
                raise ValueError(f"Falta el archivo de etiquetas: {label}")
            for line_number, line in enumerate(label.read_text(encoding="utf-8-sig").splitlines(), 1):
                values = line.split()
                if not values:
                    continue
                if len(values) != 5:
                    raise ValueError(f"Formato YOLO inválido en {label}:{line_number}.")
                try:
                    class_id = int(values[0])
                    x, y, width, height = map(float, values[1:])
                except ValueError as exc:
                    raise ValueError(f"Etiqueta no numérica en {label}:{line_number}.") from exc
                coords = (x, y, width, height)
                if (
                    class_id not in names
                    or not all(math.isfinite(v) for v in coords)
                    or not all(0 <= v <= 1 for v in coords)
                    or width <= 0
                    or height <= 0
                    or x - width / 2 < 0
                    or y - height / 2 < 0
                    or x + width / 2 > 1
                    or y + height / 2 > 1
                ):
                    raise ValueError(f"Clase o caja fuera de rango en {label}:{line_number}.")
                class_counts[class_id] += 1

        missing_classes = sorted(set(names) - set(class_counts))
        if split in {"train", "val"} and missing_classes:
            raise ValueError(f"{split} no contiene instancias de estas clases: {missing_classes}")
        split_summary[split] = {
            "images": len(images),
            "boxes_per_class": {names[c]: class_counts.get(c, 0) for c in names},
            "classes_without_boxes": [names[c] for c in missing_classes],
        }
        print(f"[audit] {split}: {len(images)} imágenes; cajas por clase: {dict(class_counts)}")

    return {"dataset_root": str(dataset_root), "classes": names, "splits": split_summary}


def evaluate(model_path: Path, data_yaml: Path, imgsz: int, run_name: str) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    metrics = model.val(
        data=str(data_yaml),
        split="test",
        imgsz=imgsz,
        plots=False,
        verbose=False,
        project=str(ROOT / "training_runs" / "precision_evaluation"),
        name=run_name,
        exist_ok=False,
    )
    box = metrics.box
    per_class: dict[str, Any] = {}
    class_ids = list(getattr(box, "ap_class_index", []))
    precisions = list(getattr(box, "p", []))
    recalls = list(getattr(box, "r", []))
    ap50 = list(getattr(box, "ap50", []))
    ap5095 = list(getattr(box, "maps", []))
    for index, class_id in enumerate(class_ids):
        class_name = model.names[int(class_id)]
        per_class[class_name] = {
            "precision": float(precisions[index]) if index < len(precisions) else None,
            "recall": float(recalls[index]) if index < len(recalls) else None,
            "map50": float(ap50[index]) if index < len(ap50) else None,
            "map50_95": float(ap5095[int(class_id)]) if int(class_id) < len(ap5095) else None,
        }
    return {
        "weights": str(model_path),
        "split": "test",
        "precision_macro": float(box.mp),
        "recall_macro": float(box.mr),
        "map50": float(box.map50),
        "map50_95": float(box.map),
        "per_class": per_class,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_yaml", type=Path, help="data.yaml con train, val, test y las 7 clases")
    parser.add_argument("--baseline", type=Path, default=BASELINE_DEFAULT)
    parser.add_argument(
        "--initial",
        default="yolo26n.pt",
        help="Pesos iniciales de YOLO26; por defecto pesos preentrenados oficiales",
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="auto", help="auto, cpu, 0, etc.")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--name", default="yolo26n_precision")
    args = parser.parse_args()

    data_yaml = args.data_yaml.resolve()
    baseline = args.baseline.resolve()
    if not data_yaml.is_file():
        parser.error(f"No existe data.yaml: {data_yaml}")
    if not baseline.is_file():
        parser.error(f"No existe el modelo de referencia: {baseline}")
    if args.epochs < 1 or args.imgsz < 320 or args.batch < 1 or args.workers < 0:
        parser.error("epochs, batch e imgsz deben ser positivos (imgsz >= 320) y workers >= 0.")

    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    audit = audit_dataset(data, data_yaml)
    from ultralytics import YOLO

    model = YOLO(args.initial)
    training = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        patience=20,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        weight_decay=0.0005,
        cos_lr=True,
        warmup_epochs=3,
        seed=20261026,
        deterministic=True,
        cache=False,
        amp=True,
        pretrained=True,
        mosaic=0.30,
        close_mosaic=10,
        mixup=0.0,
        copy_paste=0.0,
        hsv_h=0.01,
        hsv_s=0.40,
        hsv_v=0.30,
        degrees=5.0,
        translate=0.05,
        scale=0.30,
        fliplr=0.5,
        flipud=0.0,
        perspective=0.0001,
        plots=True,
        save_period=10,
        project=str(ROOT / "training_runs"),
        name=args.name,
        exist_ok=False,
    )
    candidate = Path(training.save_dir) / "weights" / "best.pt"
    if not candidate.is_file():
        raise FileNotFoundError(f"Ultralytics no generó best.pt en {candidate}")

    # El conjunto test se usa solo después de finalizar el entrenamiento.
    report = {
        "status": "evaluated",
        "warning": (
            "La métrica de test solo es fiable si las cajas están revisadas por humanos, "
            "las particiones son independientes y el test no se usa para ajustar hiperparámetros."
        ),
        "audit": audit,
        "settings": {
            "initial_weights": args.initial,
            "epochs_max": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "optimizer": "AdamW",
            "lr0": 0.001,
            "mosaic": 0.30,
            "mixup": 0.0,
            "seed": 20261026,
        },
        "baseline": evaluate(baseline, data_yaml, args.imgsz, "baseline_test"),
        "candidate": evaluate(candidate, data_yaml, args.imgsz, "candidate_test"),
        "candidate_weights": str(candidate),
    }
    report["comparison"] = {
        key: {
            "baseline": report["baseline"][key],
            "candidate": report["candidate"][key],
            "delta_candidate_minus_baseline": report["candidate"][key] - report["baseline"][key],
        }
        for key in ("precision_macro", "recall_macro", "map50", "map50_95")
    }
    output = Path(training.save_dir) / "precision_comparison.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["comparison"], ensure_ascii=False, indent=2))
    print(f"Reporte completo: {output}")
    print("El modelo de producción no se ha modificado. Revisar métricas por clase y errores antes de promover el candidato.")


if __name__ == "__main__":
    main()
