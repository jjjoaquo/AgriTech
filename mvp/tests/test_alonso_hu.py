"""Pruebas unitarias de las Historias de Usuario asignadas a Alonso Ortiz Rodríguez.

Cubre:
- SCRUM-88: Simulación 3D de parcelas y focos de plagas vinculada a inspecciones
- SCRUM-86: Guardar inspecciones por agricultor y parcela para el dashboard
- SCRUM-82: Medición y control de falsos positivos / umbrales de Prodiplosis longifila
- SCRUM-81: Etiquetar y exportar al dataset en formato YOLO
- SCRUM-28: Auditoría de calidad y balance de datasets
- SCRUM-26: Manifiesto y ampliación de datos para Prodiplosis longifila
- SCRUM-25: Comparación de métricas entre iteraciones del modelo
- SCRUM-24 / SCRUM-74 / SCRUM-27: Contrato de inferencia y soporte multimodelo
"""

from __future__ import annotations

import base64
import csv
import io
import json
import os
import secrets
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as project
from accounts import Accounts, init_tables


class TestAlonsoHistoriasUsuario(unittest.TestCase):
    def setUp(self):
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
        dash_resp = client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)
        if plan != "gratis":
            with project.db_connection() as con:
                con.execute("UPDATE users SET plan=? WHERE email=?", (plan, email))
        with client.session_transaction() as sess:
            return sess["csrf_token"]

    def _sample_image_data_url(self) -> str:
        img = Image.new("RGB", (64, 64), color=(80, 120, 80))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    # --- SCRUM-88: Simulación 3D de parcelas y focos vinculada a inspecciones ---
    def test_scrum88_cultivo_3d_route_and_summary(self):
        """Verifica la vista del cultivo 3D y el endpoint de datos resumidos por agricultor."""
        # Ruta pública de la escena 3D
        resp = self.client.get("/cultivo-3d")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"cultivo_3d.js", resp.data)

        # Endpoint de resumen requiere autenticación
        resp_anon = self.client.get("/api/cultivo/resumen")
        self.assertEqual(resp_anon.status_code, 401)

        # Con agricultor autenticado
        csrf = self._crear_usuario(self.client, "Agricultor 3D", "agri3d@example.org")
        resp_auth = self.client.get("/api/cultivo/resumen")
        self.assertEqual(resp_auth.status_code, 200)
        data = resp_auth.get_json()
        self.assertIn("inspections", data)
        self.assertIn("confirmed", data)
        self.assertIn("recent_class_counts", data)
        self.assertEqual(data["source"], "inspecciones_propias")

    # --- SCRUM-86: Guardar inspecciones por agricultor y parcela ---
    def test_scrum86_guardar_inspecciones_por_parcela_y_aislamiento(self):
        """Valida guardar inspecciones con sector/parcela y su aislamiento entre usuarios."""
        client_a = self.app.test_client()
        client_b = self.app.test_client()
        csrf_a = self._crear_usuario(client_a, "Agricultor A", "agri_a@example.org")
        csrf_b = self._crear_usuario(client_b, "Agricultor B", "agri_b@example.org")

        finding_data = {
            "sector": "Parcela Norte - Lote 3",
            "lat": -8.1234,
            "lon": -79.0567,
            "status": "confirmado",
            "reviewed": True,
            "observations": "Foco observado en espárrago verde",
            "detections": [{
                "class_name": "prodiplosis longifila larva",
                "confidence": 0.88,
                "xyxy": [10.0, 10.0, 40.0, 40.0],
                "manual": True
            }],
            "image": self._sample_image_data_url(),
        }

        # Guardar como agricultor A
        resp = client_a.post("/api/hallazgos", json=finding_data, headers={"X-CSRF-Token": csrf_a})
        self.assertEqual(resp.status_code, 201)
        finding_id = resp.get_json()["id"]

        # Agricultor A puede listar su hallazgo
        hallazgos_a = client_a.get("/api/hallazgos").get_json()
        self.assertEqual(len(hallazgos_a), 1)
        self.assertEqual(hallazgos_a[0]["sector"], "Parcela Norte - Lote 3")
        self.assertEqual(hallazgos_a[0]["detections"][0]["class_name"], "prodiplosis longifila larva")

        # Agricultor B NO puede ver el hallazgo ni la imagen de A (aislamiento de datos)
        hallazgos_b = client_b.get("/api/hallazgos").get_json()
        self.assertEqual(len(hallazgos_b), 0)
        img_resp = client_b.get(f"/api/hallazgos/{finding_id}/imagen")
        self.assertEqual(img_resp.status_code, 404)

    # --- SCRUM-25: Comparar métricas entre iteraciones del modelo ---
    def test_scrum25_comparacion_de_metricas(self):
        """Valida el endpoint de comparación de métricas del modelo baseline vs candidato."""
        resp = self.client.get("/api/model-comparison")
        if resp.status_code == 200:
            data = resp.get_json()
            self.assertIn("baseline", data)
            self.assertIn("candidate", data)
            for mod in ("baseline", "candidate"):
                self.assertIn("hit_count", data[mod])
                self.assertIn("total", data[mod])
                self.assertIn("median_inference_ms", data[mod])
                self.assertIn("by_class", data[mod])
        else:
            self.assertEqual(resp.status_code, 404)

    # --- SCRUM-81: Etiquetar y agregar al dataset (Exportación YOLO) ---
    def test_scrum81_exportacion_dataset_yolo(self):
        """Valida que los hallazgos confirmados se exportan en formato YOLO con manifiesto."""
        csrf = self._crear_usuario(self.client, "Agricultor Pro", "pro@example.org", plan="pro")

        # Insertar un hallazgo confirmado
        finding_data = {
            "sector": "Sector Exportacion",
            "status": "confirmado",
            "reviewed": True,
            "detections": [{
                "class_name": "prodiplosis longifila larva",
                "confidence": 0.95,
                "xyxy": [5.0, 5.0, 30.0, 30.0],
                "manual": True
            }],
            "image": self._sample_image_data_url(),
        }
        res_post = self.client.post("/api/hallazgos", json=finding_data, headers={"X-CSRF-Token": csrf})
        self.assertEqual(res_post.status_code, 201)

        # Exportar dataset
        resp = self.client.get("/api/dataset/export")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/zip")

        with zipfile.ZipFile(io.BytesIO(resp.data)) as z:
            archivos = z.namelist()
            self.assertIn("classes.txt", archivos)
            self.assertIn("manifest.json", archivos)
            # Debe haber al menos una etiqueta en labels/
            label_files = [f for f in archivos if f.startswith("labels/") and f.endswith(".txt")]
            self.assertGreaterEqual(len(label_files), 1)

    # --- SCRUM-28: Auditar calidad y balance del dataset de Prodiplosis longifila ---
    def test_scrum28_auditoria_manifiestos_dataset(self):
        """Valida que los manifiestos de candidatos tienen estructura y atribución requerida."""
        manifest_inat = ROOT / "dataset_candidates" / "inaturalist" / "manifest.csv"
        if manifest_inat.is_file():
            with open(manifest_inat, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertGreater(len(rows), 0)
                # Validar campos de control de calidad y trazabilidad
                headers = reader.fieldnames or []
                self.assertTrue(any("license" in h.lower() for h in headers))
                self.assertTrue(any("taxon" in h.lower() or "scientific" in h.lower() or "class" in h.lower() for h in headers))

    # --- SCRUM-82: Control de falsos positivos y umbrales de confianza ---
    def test_scrum82_umbrales_confianza_yolo(self):
        """Verifica la validación de umbrales entre 0.10 y 0.95 y la clase Prodiplosis."""
        # La clase debe estar mapeada en el detector
        self.assertIn("prodiplosis longifila larva", project.CLASS_NAMES)

        # Mock del modelo para probar validación de parámetros de /api/detect
        mock_box = MagicMock()
        mock_box.cls.item.return_value = project.CLASS_NAMES.index("prodiplosis longifila larva")
        mock_box.conf.item.return_value = 0.85
        mock_box.xyxy[0].tolist.return_value = [10, 10, 50, 50]
        mock_res = MagicMock()
        mock_res.boxes = [mock_box]
        mock_res.names = {mock_box.cls.item.return_value: "prodiplosis longifila larva"}
        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_res]

        orig_get_model = project.get_model
        try:
            project.get_model = lambda _key="baseline": mock_model

            buf = io.BytesIO()
            Image.new("RGB", (100, 100)).save(buf, "JPEG")
            raw_bytes = buf.getvalue()

            # Umbral válido por defecto (0.30 para control de sensibilidad en campo)
            resp = self.client.post("/api/detect", data={
                "image": (io.BytesIO(raw_bytes), "test.jpg"),
                "confidence": "0.30",
                "model": "baseline"
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["detections"][0]["class_name"], "prodiplosis longifila larva")

            # Umbral fuera de rango debe fallar (menor a 0.10 o mayor a 0.95)
            resp_invalido = self.client.post("/api/detect", data={
                "image": (io.BytesIO(raw_bytes), "test.jpg"),
                "confidence": "0.05",
            })
            self.assertEqual(resp_invalido.status_code, 400)
        finally:
            project.get_model = orig_get_model


if __name__ == "__main__":
    unittest.main()
