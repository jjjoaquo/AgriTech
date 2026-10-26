"""Extrae solo los pesos del checkpoint ResNet entregado por el equipo."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import torch
from safetensors.torch import save_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Checkpoint .pth original")
    parser.add_argument("destination", type=Path, help="Salida .safetensors")
    args = parser.parse_args()
    checkpoint = torch.load(args.source, map_location="cpu", weights_only=True, mmap=True)
    state = checkpoint["model_state_dict"]
    if tuple(state["fc.weight"].shape) != (102, 2048) or tuple(state["fc.bias"].shape) != (102,):
        raise ValueError("El checkpoint no corresponde al clasificador ResNet‑152 de 102 clases.")
    hasher = hashlib.sha256()
    with args.source.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    save_file({key: value.contiguous() for key, value in state.items()}, str(args.destination),
              metadata={"architecture": "resnet152", "classes": "102", "source_sha256": digest})
    print(f"Pesos convertidos: {args.destination} ({args.destination.stat().st_size} bytes)")
    print(f"Checkpoint de origen SHA‑256: {digest}")


if __name__ == "__main__":
    main()
