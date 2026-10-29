"""Pruebas estructurales de UX/UI vinculadas a SCRUM-18/19/20/21/23/87/89.

Ejecución: desde mvp/, python -m unittest discover -s tests -p 'test_ux_jira.py' -v
Estas pruebas NO sustituyen una prueba de navegador, APIs, SIGIA o modelos IA.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / 'templates'
S = ROOT / 'static'


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


def tags(name):
    tree = Tags()
    tree.feed((T / name).read_text(encoding='utf-8'))
    return tree.items


def source(path):
    return path.read_text(encoding='utf-8')


class UXJiraTests(unittest.TestCase):
    def test_scrum18_upload_has_label_and_constraints(self):
        doc = tags('index.html')
        fields = [a for tag, a in doc if tag == 'input' and a.get('id') == 'photoInput']
        self.assertEqual(1, len(fields))
        self.assertEqual('file', fields[0].get('type'))
        self.assertEqual('image/*', fields[0].get('accept'))
        self.assertTrue(fields[0].get('aria-label'))
        self.assertRegex(source(S / 'app.js'), r'10\s*\*\s*1024\s*\*\s*1024')

    def test_scrum19_busy_state_is_accessible(self):
        doc = tags('index.html')
        progress = [a for tag, a in doc if a.get('id') == 'analysisProgress']
        self.assertEqual(1, len(progress))
        self.assertEqual('status', progress[0].get('role'))
        self.assertEqual('polite', progress[0].get('aria-live'))
        script = source(S / 'app.js')
        self.assertIn("setAttribute('aria-busy',String(busy))", script)
        self.assertIn('Preparando imagen…', script)

    def test_scrum20_history_private_and_empty_state(self):
        script = source(S / 'app.js')
        self.assertIn('window.AGRI_LOGGED_IN', source(T / 'index.html'))
        self.assertIn('Inicia sesión para ver tu historial privado.', script)
        self.assertIn('Aún no tienes hallazgos guardados.', script)
        self.assertIn("link.href='#inspeccion'", script)

    def test_scrum21_detection_and_sigia_source_disclosed(self):
        script = source(S / 'app.js')
        self.assertIn('Plaga consultada:', script)
        self.assertIn('Fuente: SIGIA–SENASA.', script)
        self.assertIn('Verifica la vigencia', script)
        self.assertIn('senasaResult', source(T / 'index.html'))

    def test_scrum23_table_search_empty_state(self):
        doc = tags('index.html')
        headers = [tag for tag, a in doc if tag == 'th']
        self.assertGreaterEqual(len(headers), 6)
        self.assertTrue(any(a.get('id') == 'productsBody' for tag, a in doc))
        self.assertTrue(any(a.get('id') == 'productsScrollHelp' for tag, a in doc))
        script = source(S / 'app.js')
        self.assertIn('Sin coincidencias. Prueba otro término.', script)
        self.assertIn("String(v || '')", script)

    def test_scrum87_chart_uses_saved_dates_not_random(self):
        dashboard = source(T / 'dashboard.html')
        self.assertIn('id="trendBars"', dashboard)
        self.assertIn("findings | map(attribute='created_at')", dashboard)
        self.assertIn('new Map()', dashboard)
        self.assertNotIn('Math.random(', dashboard)
        self.assertIn('No representa necesariamente el historial completo', dashboard)
        self.assertIn('statuses.get(', dashboard)

    def test_scrum89_three_plans_and_protected_form(self):
        plans = source(T / 'plans.html')
        doc = tags('plans.html')
        cards = [a for tag, a in doc if tag == 'article' and 'plan-card' in a.get('class', '').split()]
        self.assertEqual(3, len(cards))
        self.assertIn('name="csrf_token"', plans)
        self.assertIn('action="/planes/solicitar"', plans)
        self.assertIn('todavía no procesa pagos', plans)

    def test_templates_parse_as_jinja(self):
        from jinja2 import Environment
        env = Environment()
        for path in T.glob('*.html'):
            with self.subTest(template=path.name):
                env.parse(source(path))

    def test_javascript_syntax_when_node_available(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js no instalado en el entorno')
        for path in [S / 'app.js', S / 'general.js']:
            with self.subTest(script=path.name):
                run = subprocess.run([node, '--check', str(path)], capture_output=True, text=True)
                self.assertEqual(0, run.returncode, run.stderr)


if __name__ == '__main__':
    unittest.main()
