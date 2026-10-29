"""Prueba local del flujo de detección, revisión y exportación."""

from __future__ import annotations

import base64
import io
import re
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

import app as project


def main() -> None:
    simulated_detector = not project.MODEL_PATH.is_file()
    if simulated_detector:
        # El repositorio no almacena el peso YOLO; CI verifica el flujo HTTP
        # con la misma estructura de salida que entrega el detector.
        box = MagicMock()
        box.cls.item.return_value = 0
        box.conf.item.return_value = 0.875
        box.xyxy[0].tolist.return_value = [20, 30, 100, 140]
        result = MagicMock()
        result.boxes = [box]
        result.names = {0: project.CLASS_NAMES[0]}
        model = MagicMock()
        model.predict.return_value = [result]
        project.get_model = lambda _key="baseline": model
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project.DATA_DIR = root
        project.IMAGE_DIR = root / "hallazgos"
        project.DB_PATH = root / "hallazgos.sqlite3"
        project.init_db()
        client = project.app.test_client()
        other = project.app.test_client()
        assert client.get("/").status_code == 200
        assert b"Clasificaci" in client.get("/").data
        assert client.get("/general").status_code == 200
        assert client.get("/esparrago").status_code == 200
        assert client.get("/planes").status_code == 200
        assert client.get("/cultivo-3d").status_code == 200
        assert client.get("/dashboard").status_code == 302
        assert client.get("/api/hallazgos").status_code == 401
        assert client.get("/api/dataset/export").status_code == 401
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

        def register(browser, email):
            assert browser.get("/registro").status_code == 200
            with browser.session_transaction() as sess:
                token = sess["csrf_token"]
            response = browser.post("/registro", data={"name": email.split("@")[0], "email": email,
                                                       "password": "Contraseña-De-Prueba-2026", "csrf_token": token})
            assert response.status_code == 302, response.data
            assert browser.get("/dashboard").status_code == 200
            with browser.session_transaction() as sess:
                return sess["csrf_token"]

        csrf = register(client, "uno@example.org")
        other_csrf = register(other, "dos@example.org")
        assert client.get("/dashboard").status_code == 200
        assert other.get("/dashboard").status_code == 200
        assert client.post("/api/hallazgos", json={}).status_code == 400  # CSRF obligatorio

        body = {
            "sector": "Lote de prueba", "status": "confirmado", "reviewed": False,
            "detections": [{"class_name": project.CLASS_NAMES[0], "confidence": 0,
                            "xyxy": [20, 30, 100, 140], "manual": True}],
            "image": "data:image/jpeg;base64," + base64.b64encode(raw).decode(),
        }
        assert client.post("/api/hallazgos", json=body, headers={"X-CSRF-Token": csrf}).status_code == 400
        body["reviewed"] = True
        saved = client.post("/api/hallazgos", json=body, headers={"X-CSRF-Token": csrf})
        assert saved.status_code == 201, (saved.status_code, saved.data[:500])
        findings = client.get("/api/hallazgos").json
        assert len(findings) == 1 and findings[0]["detections"][0]["manual"]
        assert other.get("/api/hallazgos").json == []
        assert other.get(f"/api/hallazgos/{saved.json['id']}/imagen").status_code == 404
        assert other.get("/api/dataset/export").status_code == 403
        assert client.get("/api/cultivo/resumen").json["inspections"] == 1
        assert other.get("/api/cultivo/resumen").json["inspections"] == 0
        assert client.get("/api/dataset/export").status_code == 403

        for _ in range(9):
            assert client.post("/api/hallazgos", json=body, headers={"X-CSRF-Token": csrf}).status_code == 201
        assert client.post("/api/hallazgos", json=body, headers={"X-CSRF-Token": csrf}).status_code == 429
        assert client.post("/planes/solicitar", data={"plan": "pro", "csrf_token": csrf}).status_code == 302

        cli = project.app.test_cli_runner().invoke(args=["bootstrap-admin", "admin@example.org"])
        assert cli.exit_code == 0, cli.output
        path = re.search(r"(/admin/activar/\S+)", cli.output).group(1)
        admin = project.app.test_client()
        assert admin.get(path).status_code == 200
        with admin.session_transaction() as sess:
            admin_csrf = sess["csrf_token"]
        assert admin.post(path, data={"password": "Admin-Contrasena-Segura-2026", "csrf_token": admin_csrf}).status_code == 302
        assert admin.get("/admin").status_code == 200
        with admin.session_transaction() as sess:
            admin_csrf = sess["csrf_token"]
        assert admin.get(f"/api/hallazgos/{saved.json['id']}/imagen").status_code == 404
        with project.db_connection() as con:
            request_id = con.execute("SELECT id FROM plan_requests WHERE plan='pro'").fetchone()[0]
        assert admin.post(f"/admin/planes/{request_id}", data={"decision": "aprobado", "csrf_token": admin_csrf}).status_code == 302
        assert client.post("/api/hallazgos", json=body, headers={"X-CSRF-Token": csrf}).status_code == 201
        export = client.get("/api/dataset/export")
        assert export.status_code == 200
        with zipfile.ZipFile(io.BytesIO(export.data)) as archive:
            label = archive.read(f"labels/{saved.json['id']}.txt").decode()
            assert label.startswith("0 ")
            assert saved.json["id"] in archive.read("manifest.json").decode()
        assert other.get("/api/hallazgos").json == []
        detector_label = "YOLO simulado" if simulated_detector else "YOLO real"
        print(f"OK: {detector_label}, registro, aislamiento, CSRF, cuota, planes, superadmin y exportación privada")


if __name__ == "__main__":
    main()
