"""Reentrena ResNet-152 con el ZIP balanceado y compara contra el peso vigente.

El conjunto de prueba se evalúa una sola vez, tras seleccionar la época por F1
macro de validación. Nunca instala automáticamente un peso en producción.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import time
import zipfile
from collections import Counter
from pathlib import Path

import torch
from PIL import Image
from safetensors.torch import load_file, save_file
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import transforms
from torchvision.models import resnet152

CLASSES = 102
NORMALIZE = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_zip(path: Path) -> dict[str, list[tuple[str, int]]]:
    samples = {split: [] for split in ("train", "val", "test")}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            parts = info.filename.replace("\\", "/").split("/")
            if len(parts) != 4 or parts[0] != "dataset_balanced_stylegan2" or parts[1] not in samples:
                raise ValueError(f"Ruta inesperada en el ZIP: {info.filename}")
            if not parts[3].lower().endswith((".jpg", ".jpeg", ".png")):
                raise ValueError(f"Archivo inesperado en el ZIP: {info.filename}")
            label = int(parts[2])
            if not 0 <= label < CLASSES:
                raise ValueError(f"Clase fuera del rango 0-101: {info.filename}")
            samples[parts[1]].append((info.filename, label))
    for split, entries in samples.items():
        if set(label for _, label in entries) != set(range(CLASSES)):
            raise ValueError(f"Faltan clases en {split}")
    names = {split: {name.rsplit("/", 1)[-1] for name, _ in entries} for split, entries in samples.items()}
    if any(names[a] & names[b] for a, b in (("train", "val"), ("train", "test"), ("val", "test"))):
        raise ValueError("Hay nombres de imagen repetidos entre conjuntos; revisar posible fuga de datos.")
    return samples


class ZipImages(Dataset):
    def __init__(self, path: Path, entries: list[tuple[str, int]], training: bool, size: int):
        self.path = path
        self.entries = entries
        self.archive = None
        self.transform = transforms.Compose([
            transforms.Resize((size, size)),
            *([transforms.RandomHorizontalFlip()] if training else []),
            transforms.ToTensor(), NORMALIZE,
        ])

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int):
        if self.archive is None:
            self.archive = zipfile.ZipFile(self.path)
        name, label = self.entries[index]
        with Image.open(io.BytesIO(self.archive.read(name))) as image:
            return self.transform(image.convert("RGB")), label

    def __getstate__(self):
        state = self.__dict__.copy()
        state["archive"] = None  # Cada trabajador abre su propio descriptor del ZIP.
        return state


def metrics(confusion: torch.Tensor) -> dict:
    count = confusion.sum(dim=1).float()
    true_positive = confusion.diag().float()
    precision = true_positive / confusion.sum(dim=0).float().clamp(min=1)
    recall = true_positive / count.clamp(min=1)
    f1 = 2 * precision * recall / (precision + recall).clamp(min=1e-12)
    return {
        "total": int(confusion.sum()),
        "accuracy": round(float(true_positive.sum() / confusion.sum().clamp(min=1)), 6),
        "balanced_accuracy": round(float(recall.mean()), 6),
        "macro_f1": round(float(f1.mean()), 6),
        "per_class_recall": [round(float(value), 6) for value in recall],
        "per_class_count": [int(value) for value in count],
    }


def run_epoch(model, loader, device, optimizer=None, scaler=None, *, confusion=None,
              loss_sum=0.0, checkpoint=None, start_batch=0) -> dict:
    training = optimizer is not None
    model.train(training)
    # Los BatchNorm preentrenados se mantienen fijos en ambas etapas.
    if training:
        for module in model.modules():
            if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
                module.eval()
    if confusion is None:
        confusion = torch.zeros((CLASSES, CLASSES), dtype=torch.int64)
    for batch_number, (images, labels) in enumerate(loader, start=start_batch):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training), torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(images)
            loss = torch.nn.functional.cross_entropy(logits, labels)
        if training:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        loss_sum += float(loss.detach()) * len(labels)
        predictions = logits.argmax(dim=1)
        indices = (labels * CLASSES + predictions).cpu()
        confusion += torch.bincount(indices, minlength=CLASSES * CLASSES).reshape(CLASSES, CLASSES)
        if checkpoint is not None:
            checkpoint(batch_number + 1, confusion, loss_sum)
    result = metrics(confusion)
    result["loss"] = round(loss_sum / max(result["total"], 1), 6)
    return result


def build_model(weights: Path) -> torch.nn.Module:
    model = resnet152(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, CLASSES)
    state = load_file(str(weights), device="cpu")
    model.load_state_dict(state, strict=True)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True, help="Peso .safetensors instalado actualmente")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-epochs", type=int, default=2)
    parser.add_argument("--fine-epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--allow-cpu", action="store_true", help="Permite entrenamiento completo sin CUDA (puede tardar muchas horas)")
    parser.add_argument("--smoke", action="store_true", help="Prueba técnica reducida; no produce modelo final")
    parser.add_argument("--checkpoint-batches", type=int, default=250,
                        help="Guardar reanudación cada N lotes de entrenamiento")
    args = parser.parse_args()
    if args.head_epochs < 0 or args.fine_epochs < 0 or args.head_epochs + args.fine_epochs == 0:
        parser.error("Debe haber al menos una época de entrenamiento.")
    if args.batch_size < 1 or args.workers < 0 or args.checkpoint_batches < 1:
        parser.error("Lote y trabajadores deben ser válidos.")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    samples = scan_zip(args.dataset)
    if args.smoke:
        samples = {split: [entry for label in (0, 1)
                           for entry in [item for item in entries if item[1] == label][:2]]
                   for split, entries in samples.items()}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Dispositivo: {device}; imágenes: " + ", ".join(f"{key}={len(value)}" for key, value in samples.items()), flush=True)
    if device.type == "cpu" and not (args.smoke or args.allow_cpu):
        raise RuntimeError("Para ejecutar ResNet-152 completo sin CUDA, indica --allow-cpu.")
    args.output.mkdir(parents=True, exist_ok=True)
    size = 256
    loaders = {
        split: DataLoader(ZipImages(args.dataset, entries, split == "train", size),
                          batch_size=args.batch_size, shuffle=split == "train", num_workers=args.workers,
                          pin_memory=device.type == "cuda")
        for split, entries in samples.items()
    }
    model = build_model(args.baseline).to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    best_f1 = -1.0
    history = []
    candidate_path = args.output / "best_resnet152_balanced_candidate.safetensors"
    checkpoint_path = args.output / "training_checkpoint.pt"
    start_epoch = 0
    resume = None
    if checkpoint_path.exists():
        resume = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        if (resume["dataset_path"] != str(args.dataset.resolve()) or
                resume["baseline_path"] != str(args.baseline.resolve()) or
                resume["batch_size"] != args.batch_size or
                resume["head_epochs"] != args.head_epochs or
                resume["fine_epochs"] != args.fine_epochs or
                resume["seed"] != args.seed):
            raise ValueError("El checkpoint no coincide con los parámetros de este entrenamiento.")
        model.load_state_dict(resume["model"])
        start_epoch = resume["epoch"]
        best_f1 = resume["best_f1"]
        history = resume["history"]
        print(f"Reanudando época {start_epoch + 1} desde imagen {resume['next_index']}", flush=True)

    def save_checkpoint(epoch, next_index, confusion, loss_sum, optimizer):
        payload = {
            "dataset_path": str(args.dataset.resolve()), "baseline_path": str(args.baseline.resolve()),
            "batch_size": args.batch_size, "head_epochs": args.head_epochs,
            "fine_epochs": args.fine_epochs, "seed": args.seed, "epoch": epoch,
            "next_index": next_index, "confusion": confusion, "loss_sum": loss_sum,
            "model": model.state_dict(), "optimizer": optimizer.state_dict() if optimizer else None,
            "best_f1": best_f1, "history": history,
        }
        temporary = checkpoint_path.with_suffix(".tmp")
        torch.save(payload, temporary)
        os.replace(temporary, checkpoint_path)

    for epoch in range(start_epoch, args.head_epochs + args.fine_epochs):
        fine = epoch >= args.head_epochs
        for parameter in model.parameters():
            parameter.requires_grad = False
        for parameter in model.fc.parameters():
            parameter.requires_grad = True
        if fine:
            for parameter in model.layer4.parameters():
                parameter.requires_grad = True
        optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),
                                      lr=1e-5 if fine else 1e-3, weight_decay=1e-4)
        next_index = resume["next_index"] if resume is not None and epoch == start_epoch else 0
        initial_confusion = resume["confusion"] if next_index else None
        initial_loss = resume["loss_sum"] if next_index else 0.0
        if next_index and resume["optimizer"] is not None:
            optimizer.load_state_dict(resume["optimizer"])
        order = torch.randperm(len(samples["train"]), generator=torch.Generator().manual_seed(args.seed + epoch)).tolist()
        remaining = Subset(loaders["train"].dataset, order[next_index:])
        train_loader = DataLoader(remaining, batch_size=args.batch_size, shuffle=False,
                                  num_workers=args.workers, pin_memory=device.type == "cuda")
        start = time.monotonic()
        total_batches = (len(samples["train"]) + args.batch_size - 1) // args.batch_size

        def maybe_checkpoint(batch_number, confusion, loss_sum):
            if batch_number % args.checkpoint_batches == 0 or batch_number == total_batches:
                processed = min(batch_number * args.batch_size, len(samples["train"]))
                save_checkpoint(epoch, processed, confusion, loss_sum, optimizer)
                print(f"Época {epoch + 1}: {processed}/{len(samples['train'])} imágenes", flush=True)

        train = run_epoch(model, train_loader, device, optimizer, scaler,
                          confusion=initial_confusion, loss_sum=initial_loss,
                          checkpoint=maybe_checkpoint, start_batch=next_index // args.batch_size)
        validation = run_epoch(model, loaders["val"], device)
        record = {"epoch": epoch + 1, "stage": "layer4+head" if fine else "head", "train": train,
                  "validation": validation, "seconds": round(time.monotonic() - start)}
        history.append(record)
        print(f"Época {epoch + 1}: val F1 macro={validation['macro_f1']:.4f}, "
              f"acc={validation['accuracy']:.4f}, duración={record['seconds']}s", flush=True)
        if validation["macro_f1"] > best_f1:
            best_f1 = validation["macro_f1"]
            save_file({key: value.detach().cpu().contiguous() for key, value in model.state_dict().items()},
                      str(candidate_path), metadata={"architecture": "resnet152", "classes": "102",
                      "image_size": "256", "training": "ip102_balanced_stylegan2",
                      "baseline_sha256": sha256(args.baseline), "best_epoch": str(epoch + 1)})
        save_checkpoint(epoch + 1, 0, torch.zeros((CLASSES, CLASSES), dtype=torch.int64), 0.0, None)
        resume = None
    # El conjunto test solo se usa después de fijar la época por validación.
    candidate = build_model(candidate_path).to(device)
    candidate_test = run_epoch(candidate, loaders["test"], device)
    del candidate
    baseline = build_model(args.baseline).to(device)
    baseline_test = run_epoch(baseline, loaders["test"], device)
    report = {
        "status": "smoke_only" if args.smoke else "completed",
        "dataset_sha256": sha256(args.dataset), "baseline_sha256": sha256(args.baseline),
        "split_counts": {key: len(value) for key, value in samples.items()},
        "synthetic_train_count": sum("synth_stylegan2_" in name for name, _ in samples["train"]),
        "image_size": size, "seed": args.seed, "history": history,
        "candidate_test": candidate_test, "baseline_test": baseline_test,
        "candidate_improves_macro_f1": candidate_test["macro_f1"] > baseline_test["macro_f1"],
        "candidate_path": str(candidate_path),
    }
    (args.output / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoint_path.unlink(missing_ok=True)
    print(f"Comparación guardada en {args.output / 'comparison.json'}", flush=True)
    if not args.smoke and not report["candidate_improves_macro_f1"]:
        print("El candidato no supera al peso publicado; no desplegar.", flush=True)


if __name__ == "__main__":
    main()
