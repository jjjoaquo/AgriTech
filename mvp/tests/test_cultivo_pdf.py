"""Pruebas unitarias y de integración para el análisis de PDF y visualización 3D."""

from __future__ import annotations

import base64
import io
import json
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image
import pypdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pdf_processor

try:
    import app as project
except ImportError:
    project = None


class TestPdfProcessor(unittest.TestCase):
    """Pruebas del módulo de extracción y procesamiento de reportes PDF."""

    def _create_sample_pdf(self, images: list[Image.Image]) -> bytes:
        if not images:
            buf = io.BytesIO()
            writer = pypdf.PdfWriter()
            writer.add_blank_page(width=200, height=200)
            writer.write(buf)
            return buf.getvalue()

        buf = io.BytesIO()
        first, rest = images[0], images[1:]
        first.save(buf, format="PDF", save_all=True, append_images=rest)
        return buf.getvalue()

    def test_extract_images_from_pdf_success(self):
        img1 = Image.new("RGB", (100, 100), color="green")
        img2 = Image.new("RGB", (150, 120), color="blue")
        pdf_bytes = self._create_sample_pdf([img1, img2])

        extracted = pdf_processor.extract_images_from_pdf(pdf_bytes)
        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0].size, (100, 100))
        self.assertEqual(extracted[1].size, (150, 120))

    def test_extract_images_from_pdf_empty_or_invalid(self):
        with self.assertRaises(ValueError):
            pdf_processor.extract_images_from_pdf(b"")

        with self.assertRaises(ValueError):
            pdf_processor.extract_images_from_pdf(b"not-a-pdf-file")

        empty_pdf = self._create_sample_pdf([])
        with self.assertRaises(ValueError):
            pdf_processor.extract_images_from_pdf(empty_pdf)

    def test_extract_images_filters_tiny_icons(self):
        large = Image.new("RGB", (160, 160), color="green")
        tiny = Image.new("RGB", (20, 20), color="red")
        pdf_bytes = self._create_sample_pdf([large, tiny])

        extracted = pdf_processor.extract_images_from_pdf(pdf_bytes, min_side=48)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0].size, (160, 160))

    def test_image_to_base64_data_url(self):
        img = Image.new("RGB", (64, 64), color="forestgreen")
        data_url = pdf_processor.image_to_base64_data_url(img)
        self.assertTrue(data_url.startswith("data:image/jpeg;base64,"))


class TestCultivo3DEndpoints(unittest.TestCase):
    """Pruebas de los endpoints de Flask para el análisis 3D y guardado de lotes."""

    def setUp(self):
        if project is None:
            self.skipTest("Flask no está instalado en este entorno local (se ejecuta en CI de GitHub Actions).")

        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.prev_data_dir = project.DATA_DIR
        self.prev_image_dir = project.IMAGE_DIR
        self.prev_db_path = project.DB_PATH

        project.DATA_DIR = self.data_dir
        project.IMAGE_DIR = self.data_dir / "hallazgos"
        project.DB_PATH = self.data_dir / "hallazgos.sqlite3"
        project.init_db()

        self.app = project.create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        if project is None:
            return
        project.DATA_DIR = self.prev_data_dir
        project.IMAGE_DIR = self.prev_image_dir
        project.DB_PATH = self.prev_db_path
        self.temp_dir.cleanup()

    def _crear_usuario(self, client, nombre: str, email: str, plan: str = "gratis") -> str:
        with client.session_transaction() as sess:
            token = sess["csrf_token"] if "csrf_token" in sess else secrets.token_urlsafe(32)
            sess["csrf_token"] = token
        resp = client.post("/registro", data={
            "name": nombre,
            "email": email,
            "password": "Password-Seguro-2026",
            "csrf_token": token,
        })
        self.assertEqual(resp.status_code, 302)
        dash = client.get("/dashboard")
        self.assertEqual(dash.status_code, 200)
        if plan != "gratis":
            with project.db_connection() as con:
                con.execute("UPDATE users SET plan=? WHERE email=?", (plan, email))
        with client.session_transaction() as sess:
            return sess["csrf_token"]

    def _sample_pdf_bytes(self, count: int = 3) -> bytes:
        images = [Image.new("RGB", (80, 80), color=(50 + i * 30, 100, 50)) for i in range(count)]
        buf = io.BytesIO()
        images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
        return buf.getvalue()

    def test_cultivo_3d_page_renders_with_new_features(self):
        resp = self.client.get("/cultivo-3d")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"formAnalizarPdf", resp.data)
        self.assertIn(b"btnModeCamas", resp.data)
        self.assertIn(b"btnModeGrid", resp.data)
        self.assertIn(b"plantModal", resp.data)

    def test_analizar_pdf_auth_and_validation(self):
        # 1. Sin autenticación -> 401
        resp = self.client.post("/api/cultivo/analizar-pdf")
        self.assertEqual(resp.status_code, 401)

        # 2. Con autenticación pero sin archivo -> 400
        csrf = self._crear_usuario(self.client, "Agricultor PDF", "pdf@example.org")
        resp = self.client.post("/api/cultivo/analizar-pdf", headers={"X-CSRF-Token": csrf})
        self.assertEqual(resp.status_code, 400)

        # 3. Confianza fuera de rango -> 400
        pdf_data = self._sample_pdf_bytes(2)
        resp = self.client.post(
            "/api/cultivo/analizar-pdf",
            headers={"X-CSRF-Token": csrf},
            data={"reporte": (io.BytesIO(pdf_data), "test.pdf"), "confidence": "0.02"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_analizar_pdf_success_with_yolo_mock(self):
        csrf = self._crear_usuario(self.client, "Agricultor YOLO", "yolo3d@example.org")
        pdf_data = self._sample_pdf_bytes(3)

        # Mock del detector YOLO para simular 1 planta con plaga y 2 sanas
        mock_box = MagicMock()
        mock_box.cls.item.return_value = 0
        mock_box.conf.item.return_value = 0.82
        mock_box.xyxy[0].tolist.return_value = [10, 10, 40, 40]

        mock_res_alert = MagicMock()
        mock_res_alert.boxes = [mock_box]
        mock_res_alert.names = {0: project.CLASS_NAMES[0]}

        mock_res_clean = MagicMock()
        mock_res_clean.boxes = []
        mock_res_clean.names = {0: project.CLASS_NAMES[0]}

        model = MagicMock()
        model.predict.side_effect = [[mock_res_alert], [mock_res_clean], [mock_res_clean]]

        orig_get_model = project.get_model
        try:
            project.get_model = lambda _key="baseline": model

            resp = self.client.post(
                "/api/cultivo/analizar-pdf",
                headers={"X-CSRF-Token": csrf},
                data={"reporte": (io.BytesIO(pdf_data), "lote_esp.pdf"), "confidence": "0.30"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()

            self.assertTrue(data["success"])
            self.assertEqual(data["total_plants"], 3)
            self.assertEqual(data["healthy_count"], 2)
            self.assertEqual(data["infested_count"], 1)
            self.assertIn(project.CLASS_NAMES[0], data["pests_summary"])
            self.assertEqual(len(data["plants"]), 3)
            self.assertEqual(data["plants"][0]["status"], "alerta")
            self.assertEqual(data["plants"][1]["status"], "limpio")
            self.assertTrue(data["plants"][0]["image"].startswith("data:image/jpeg;base64,"))
        finally:
            project.get_model = orig_get_model

    def test_guardar_lote_opcional(self):
        csrf = self._crear_usuario(self.client, "Agricultor Guardar", "guardar@example.org")

        img = Image.new("RGB", (64, 64), color="green")
        data_url = pdf_processor.image_to_base64_data_url(img)

        sample_plants = [
            {
                "id": 1,
                "status": "alerta",
                "image": data_url,
                "detections": [{
                    "class_name": project.CLASS_NAMES[0],
                    "confidence": 0.90,
                    "xyxy": [5, 5, 30, 30]
                }]
            },
            {
                "id": 2,
                "status": "limpio",
                "image": data_url,
                "detections": []
            }
        ]

        resp = self.client.post(
            "/api/cultivo/guardar-lote",
            headers={"X-CSRF-Token": csrf},
            json={"sector": "Lote San José", "plants": sample_plants}
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data["saved_count"], 2)

        with project.db_connection() as con:
            rows = con.execute("SELECT sector, status, detections_json FROM hallazgos").fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["sector"], "Lote San José")


if __name__ == "__main__":
    unittest.main()
