"""Exporta fotos candidatas con licencia abierta desde iNaturalist.

Las anotaciones de especie y etapa NO son cajas YOLO. Se requiere revisión
humana y etiquetado de recuadros antes de usar estas fotos para entrenamiento.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from pathlib import Path

import requests
from PIL import Image


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dataset_candidates" / "inaturalist"
API = "https://api.inaturalist.org/v1/observations"
CLASSES = [
    (0, "Chloridea virescens adulto", 509353, 2),
    (1, "Chloridea virescens larva", 509353, 6),
    (2, "Chrysodeixis includens adulto", 148908, 2),
    (3, "Chrysodeixis includens larva", 148908, 6),
    (4, "Prodiplosis longifila larva", 1120241, 6),
    (5, "Spodoptera eridania adulto", 231424, 2),
    (6, "Spodoptera eridania larva", 231424, 6),
]
FIELDS = [
    "class_id", "class_name", "status", "image_file", "observation_id",
    "observation_url", "photo_id", "photo_url", "license", "attribution",
    "observer", "observed_on", "taxon", "life_stage", "width", "height",
    "sha256", "review_note",
    "asparagus_host_verified", "intended_use",
]


def get_json(session: requests.Session, params: dict) -> dict:
    for attempt in range(4):
        try:
            response = session.get(API, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def download(session: requests.Session, url: str) -> bytes:
    for attempt in range(3):
        try:
            response = session.get(url, timeout=40)
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith("image/"):
                raise ValueError("La respuesta no es una imagen")
            if len(response.content) > 12_000_000:
                raise ValueError("Imagen demasiado grande")
            return response.content
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-class", type=int, default=18)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "AsparagusResearchDataset/1.0 (academic source audit)"})
    rows: list[dict] = []
    seen_hashes: set[str] = set()
    counts: dict[str, dict] = {}

    for class_id, name, taxon_id, stage_id in CLASSES:
        folder = OUT / "images" / f"{class_id}_{name.replace(' ', '_')}"
        folder.mkdir(parents=True, exist_ok=True)
        count = 0
        page = 1
        available = None
        while count < args.per_class and page <= 5:
            params = {
                "taxon_id": taxon_id,
                "term_id": 1,
                "term_value_id": stage_id,
                "photos": "true",
                "quality_grade": "research",
                "photo_license": "cc0,cc-by",
                "per_page": 100,
                "page": page,
                "order": "asc",
                "order_by": "id",
            }
            data = get_json(session, params)
            available = data.get("total_results", 0)
            observations = data.get("results", [])
            if not observations:
                break
            for obs in observations:
                if count >= args.per_class:
                    break
                taxon = obs.get("taxon") or {}
                if taxon.get("id") != taxon_id:
                    continue
                photos = [p for p in obs.get("photos", []) if p.get("license_code") in ("cc0", "cc-by")]
                for photo in photos[:1]:
                    source_url = photo.get("url", "").replace("/square.", "/large.")
                    if not source_url.startswith("https://"):
                        continue
                    try:
                        raw = download(session, source_url)
                        with Image.open(io.BytesIO(raw)) as image:
                            image.load()
                            if min(image.size) < 400:
                                continue
                            rgb = image.convert("RGB")
                            width, height = rgb.size
                            image_bytes = io.BytesIO()
                            rgb.save(image_bytes, format="JPEG", quality=92)
                            jpg = image_bytes.getvalue()
                    except (requests.RequestException, ValueError, OSError):
                        continue
                    sha = hashlib.sha256(jpg).hexdigest()
                    if sha in seen_hashes:
                        continue
                    seen_hashes.add(sha)
                    filename = f"inat_{obs['id']}_{photo['id']}.jpg"
                    path = folder / filename
                    path.write_bytes(jpg)
                    user = obs.get("user") or {}
                    row = {
                        "class_id": class_id,
                        "class_name": name,
                        "status": "candidate_needs_bbox_and_species_review",
                        "image_file": str(path.relative_to(OUT)).replace("\\", "/"),
                        "observation_id": obs["id"],
                        "observation_url": obs.get("uri", f"https://www.inaturalist.org/observations/{obs['id']}"),
                        "photo_id": photo["id"],
                        "photo_url": source_url,
                        "license": photo["license_code"].upper(),
                        "attribution": photo.get("attribution", ""),
                        "observer": user.get("login", ""),
                        "observed_on": obs.get("observed_on", ""),
                        "taxon": taxon.get("name", ""),
                        "life_stage": "adult" if stage_id == 2 else "larva",
                        "width": width,
                        "height": height,
                        "sha256": sha,
                        "review_note": "Verify species, life stage, domain relevance, bounding boxes and license before training.",
                        "asparagus_host_verified": "no",
                        "intended_use": "species_stage_reference_pending_review",
                    }
                    rows.append(row)
                    count += 1
                    break
            page += 1
            time.sleep(0.2)
        counts[name] = {"downloaded": count, "available_observations": available or 0}
        print(f"{name}: {count} descargadas de {available or 0} observaciones posibles", flush=True)

    with (OUT / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "summary.json").write_text(
        json.dumps({"source": API, "counts": counts, "total_images": len(rows),
                    "status": "candidates_only_no_ground_truth_boxes"}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
