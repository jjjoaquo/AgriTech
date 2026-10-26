"""Prueba local del flujo de detección, revisión y exportación."""

from __future__ import annotations

import base64
import io
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

import app as project


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project.DATA_DIR = root
        project.IMAGE_DIR = root / "hallazgos"
        project.DB_PATH = root / "hallazgos.sqlite3"
        project.init_db()
        client = project.app.test_client()
        assert client.get("/").status_code == 200
        assert b"Clasificaci" in client.get("/").data
        assert client.get("/general").status_code == 200
        assert client.get("/esparrago").status_code == 200
        comparison = client.get("/api/model-comparison")
        assert comparison.status_code in (200, 404)

        image = Image.new("RGB", (320, 240), "#507e55")
        output = io.BytesIO()
        image.save(output, "JPEG")
        raw = output.getvalue()
        original_available = project.general_classifier.available
        original_classify = project.general_classifier.classify_image
        try:
            project.general_classifier.available = lambda: True
            project.general_classifier.classify_image = lambda image: {
                "predictions": [{"class_id": 0, "class_name": "rice leaf roller", "score": 0.8}],
                "class_count": 102,
            }
            general = client.post("/api/classify", data={"image": (io.BytesIO(raw), "prueba.jpg")})
            assert general.status_code == 200 and general.json["class_count"] == 102
        finally:
            project.general_classifier.available = original_available
            project.general_classifier.classify_image = original_classify
        response = client.post("/api/detect", data={"image": (io.BytesIO(raw), "prueba.jpg"), "confidence": "0.45"})
        assert response.status_code == 200, response.json
        assert response.json["width"] == 320
        assert response.json["height"] == 240
        invalid_model = client.post("/api/detect", data={"image": (io.BytesIO(raw), "prueba.jpg"), "model": "otro"})
        assert invalid_model.status_code == 400
        if project.CANDIDATE_PATH.is_file():
            candidate = client.post("/api/detect", data={"image": (io.BytesIO(raw), "prueba.jpg"), "model": "candidate"})
            assert candidate.status_code == 200, candidate.json
            assert candidate.json["model"] == project.CANDIDATE_PATH.name

        body = {
            "sector": "Lote de prueba", "status": "confirmado", "reviewed": False,
            "detections": [{"class_name": project.CLASS_NAMES[0], "confidence": 0,
                            "xyxy": [20, 30, 100, 140], "manual": True}],
            "image": "data:image/jpeg;base64," + base64.b64encode(raw).decode(),
        }
        assert client.post("/api/hallazgos", json=body).status_code == 400
        body["reviewed"] = True
        saved = client.post("/api/hallazgos", json=body)
        assert saved.status_code == 201, saved.json
        findings = client.get("/api/hallazgos").json
        assert len(findings) == 1 and findings[0]["detections"][0]["manual"]
        export = client.get("/api/dataset/export")
        assert export.status_code == 200
        with zipfile.ZipFile(io.BytesIO(export.data)) as archive:
            label = archive.read(f"labels/{saved.json['id']}.txt").decode()
            assert label.startswith("0 ")
            assert saved.json["id"] in archive.read("manifest.json").decode()
        print("OK: página, detección, revisión obligatoria, guardado y exportación YOLO")


if __name__ == "__main__":
    main()
