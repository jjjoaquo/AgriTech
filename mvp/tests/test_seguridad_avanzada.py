"""Regresiones de seguridad de autenticación y límites HTTP, sin YOLO real.

Todos los datos se aíslan en una base SQLite temporal.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app as project


class AdvancedSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = (
            project.DATA_DIR, project.IMAGE_DIR, project.PDF_DIR, project.DB_PATH
        )
        root = Path(self.temp.name)
        project.DATA_DIR = root
        project.IMAGE_DIR = root / "hallazgos"
        project.PDF_DIR = root / "senasa"
        project.DB_PATH = root / "hallazgos.sqlite3"
        self.app = project.create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        (project.DATA_DIR, project.IMAGE_DIR, project.PDF_DIR,
         project.DB_PATH) = self.original
        self.temp.cleanup()

    @staticmethod
    def csrf(client):
        client.get("/login")
        with client.session_transaction() as session:
            return session["csrf_token"]

    def register(self, email="agricultor-audit@example.org"):
        self.client.get("/registro")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        response = self.client.post("/registro", data={
            "name": "Agricultor de prueba",
            "email": email,
            "password": "Contrasena-Segura-2026",
            "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        return email

    def test_five_bad_passwords_lock_account_without_disclosing_password(self):
        email = self.register()
        browser = self.app.test_client()
        token = self.csrf(browser)
        for i in range(5):
            response = browser.post("/login", data={
                "email": email,
                "password": "incorrecta",
                "csrf_token": token,
            })
            with self.subTest(attempt=i + 1):
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/login")
        with project.db_connection() as db:
            user = db.execute(
                "SELECT failed_logins,locked_until FROM users WHERE email=?",
                (email,),
            ).fetchone()
        self.assertEqual(user["failed_logins"], 5)
        self.assertIsNotNone(user["locked_until"])

        # Mientras esté bloqueada, incluso la contraseña correcta es rechazada.
        blocked = browser.post("/login", data={
            "email": email,
            "password": "Contrasena-Segura-2026",
            "csrf_token": token,
        })
        self.assertEqual(blocked.status_code, 302)
        self.assertEqual(blocked.headers["Location"], "/login")
        self.assertEqual(browser.get("/api/hallazgos").status_code, 401)

    def test_private_responses_disable_browser_caching(self):
        self.register()
        for path in ("/dashboard", "/api/hallazgos", "/api/cultivo/resumen"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

    def test_production_requires_secret_and_secure_session_cookie(self):
        with patch.dict(os.environ, {"AGRI_ENV": "production"}, clear=False):
            with patch.dict(os.environ, {"AGRI_SECRET_KEY": ""}, clear=False):
                with self.assertRaises(RuntimeError):
                    project.create_app()
            # A production secret must be configured out of band.
            with patch.dict(os.environ, {
                "AGRI_SECRET_KEY": "test-only-not-a-production-key",
            }, clear=False):
                production_app = project.create_app()
                self.assertTrue(production_app.config["SESSION_COOKIE_SECURE"])
                self.assertTrue(production_app.config["SESSION_COOKIE_HTTPONLY"])
                self.assertEqual(
                    production_app.config["SESSION_COOKIE_SAMESITE"], "Lax"
                )

    def test_browser_permissions_are_restricted_and_private_photos_same_origin(self):
        response = self.client.get("/login")
        permissions = response.headers.get("Permissions-Policy", "")
        self.assertIn("camera=(self)", permissions)
        self.assertIn("geolocation=(self)", permissions)
        self.assertIn("microphone=()", permissions)
        self.assertIn("payment=()", permissions)
        self.assertIn("usb=()", permissions)

        self.register()
        # Cabecera defensiva incluso cuando no existe el ID solicitado.
        photo = self.client.get("/api/hallazgos/id-ficticio/imagen")
        self.assertEqual(photo.status_code, 404)
        self.assertEqual(
            photo.headers.get("Cross-Origin-Resource-Policy"), "same-origin"
        )

    def test_oversized_request_is_rejected(self):
        # Flask rejects an oversized request body before it reaches the handler.
        response = self.client.post(
            "/api/hallazgos",
            data=b"x" * (16 * 1024 * 1024 + 1),
            content_type="application/json",
        )
        # The login guard may reject unauthenticated requests earlier (401);
        # authenticate first to actually exercise the configured size limit.
        self.assertEqual(response.status_code, 401)
        self.register()
        self.client.get("/dashboard")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        response = self.client.post(
            "/api/hallazgos",
            data=b"x" * (16 * 1024 * 1024 + 1),
            content_type="application/json",
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.app.config["MAX_CONTENT_LENGTH"], 16 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
