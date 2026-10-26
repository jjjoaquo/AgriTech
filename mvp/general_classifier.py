"""Clasificador experimental de plagas agrícolas (102 clases, sin cajas)."""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
CLASSES_PATH = ROOT / "models" / "classes_ip102.txt"
DEFAULT_WEIGHTS = ROOT / "models" / "best_resnet152_baseline.safetensors"
WEIGHTS_PATH = Path(os.environ.get("AGRI_RESNET_WEIGHTS", str(DEFAULT_WEIGHTS)))
IMAGE_SIZE = int(os.environ.get("AGRI_RESNET_IMAGE_SIZE", "256"))
MODEL_NAME = "ResNet-152 · 102 clases (peso de Alonso)"

_model = None
_model_lock = threading.Lock()


def load_classes(path: Path = CLASSES_PATH) -> list[str]:
    labels: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"\s*(\d+)\s+(.+?)\s*", line)
        if not match:
            continue
        labels[int(match.group(1)) - 1] = match.group(2).strip()
    if set(labels) != set(range(102)):
        raise ValueError("La lista debe contener exactamente las clases 1 a 102.")
    return [labels[index] for index in range(102)]


def available() -> bool:
    return WEIGHTS_PATH.is_file() and CLASSES_PATH.is_file()


def get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            if not WEIGHTS_PATH.is_file():
                raise FileNotFoundError("Falta el peso ResNet en este servidor.")
            import torch
            from safetensors.torch import load_file
            from torchvision.models import resnet152

            model = resnet152(weights=None)
            model.fc = torch.nn.Linear(model.fc.in_features, 102)
            model.load_state_dict(load_file(str(WEIGHTS_PATH), device="cpu"), strict=True)
            model.eval()
            _model = model
    return _model


def classify_image(image: Image.Image, top_k: int = 3) -> dict:
    """Clasifica la imagen completa con el tamaño 256 informado por el entrenador."""
    import torch
    from torchvision import transforms

    if not 1 <= top_k <= 5:
        raise ValueError("top_k debe estar entre 1 y 5.")
    labels = load_classes()
    preprocess = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    start = time.perf_counter()
    with torch.inference_mode():
        logits = get_model()(preprocess(image.convert("RGB")).unsqueeze(0))
        scores, indices = torch.softmax(logits, dim=1).topk(top_k, dim=1)
    predictions = [
        {"class_id": int(index), "class_name": labels[int(index)], "score": round(float(score), 4)}
        for score, index in zip(scores[0], indices[0])
    ]
    return {
        "predictions": predictions,
        "inference_ms": round((time.perf_counter() - start) * 1000),
        "model": MODEL_NAME,
        "class_count": len(labels),
        "image_size": IMAGE_SIZE,
        "notice": "Clasificación de la imagen completa; no localiza plagas ni dibuja recuadros. Entrada de 256 × 256 px, según Alonso.",
    }
