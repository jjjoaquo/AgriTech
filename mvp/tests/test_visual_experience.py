"""Smoke checks for the complete public visual journey and its served media."""

from __future__ import annotations

import unittest

from app import app


class VisualExperienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_public_journey_renders(self) -> None:
        for path, expected in (
            ("/", "Observa el cultivo"),
            ("/general", "Una foto, posibles"),
            ("/esparrago", "Una mirada más precisa"),
            ("/cultivo-3d", "Inspección de Cultivo en 3D"),
            ("/planes", "Elige cómo usar AgriTech"),
            ("/login", "Continúa con tu cultivo"),
            ("/registro", "Crea tu espacio"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code)
                self.assertIn(expected, response.get_data(as_text=True))
                self.assertIn("visual-2026.css", response.get_data(as_text=True))

    def test_public_visual_media_is_served(self) -> None:
        for path, media_types in (
            ("/static/media/campo-en-movimiento.mp4", {"video/mp4"}),
            ("/static/media/demostracion-cultivo-3d.mp4", {"video/mp4"}),
            ("/static/media/campo-poster.webp", {"image/webp", "application/octet-stream"}),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                try:
                    self.assertEqual(200, response.status_code)
                    self.assertIn(response.mimetype, media_types)
                    self.assertGreater(len(response.data), 1000)
                finally:
                    response.close()

    def test_hero_has_fallback_and_3d_demo_is_labelled(self) -> None:
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("autoplay muted loop playsinline", page)
        self.assertIn("campo-poster.webp", page)
        self.assertIn("demostración ilustrativa", page)


if __name__ == "__main__":
    unittest.main()
