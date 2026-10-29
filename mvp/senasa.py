"""Consulta opcional al portal público SIGIA de SENASA.

El portal no ofrece una API documentada para este flujo. Los selectores pueden
cambiar; un error de consulta nunca debe ocultar la detección de YOLO.
"""

from __future__ import annotations

import time
from pathlib import Path

SIGIA_URL = "https://servicios.senasa.gob.pe/SIGIAWeb/sigia_consulta_plaga.html"

MAPEO_PLAGAS = {
    "spodoptera eridania adulto": ("Spodoptera eridania", False),
    "spodoptera eridania larva": ("Spodoptera eridania", False),
    "Chrysodeixis includens adulto": ("Chrysodeixis includens", False),
    "Chrysodeixis includens larva": ("Chrysodeixis includens", False),
    "Chloridea virescens adulto": ("Chloridea virescens", False),
    "Chloridea virescens larva": ("Chloridea virescens", False),
    "prodiplosis longifila larva": ("CARACHA", True),
}


def consultar_sigia(class_name: str, output_dir: Path) -> Path:
    """Busca plaga y cultivo en SIGIA; devuelve el PDF realmente descargado."""
    if class_name not in MAPEO_PLAGAS:
        raise ValueError("La clase no tiene una búsqueda configurada en SIGIA.")
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    term, common_name = MAPEO_PLAGAS[class_name]
    output_dir.mkdir(parents=True, exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("prefs", {
        "download.default_directory": str(output_dir.resolve()),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    })
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 20)
    try:
        driver.get(SIGIA_URL)
        field = "nombrecomun" if common_name else "nombrecientifico"
        wait.until(EC.presence_of_element_located((By.NAME, field))).send_keys(term)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Buscar']"))).click()
        wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//div[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{term.upper()}')]"
        ))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Ver Cultivos']"))).click()
        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//div[normalize-space()='Espárrago']/ancestor::table[contains(@class, 'x-grid3-row-table')]//div[contains(@class, 'x-grid3-check-col')]"
        ))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Ver Productos']"))).click()
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Imprimir']"))).click()
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            pdfs = list(output_dir.glob("*.pdf"))
            if pdfs and not list(output_dir.glob("*.crdownload")):
                pdf = max(pdfs, key=lambda p: p.stat().st_mtime)
                if pdf.stat().st_size > 100 and pdf.open("rb").read(5) == b"%PDF-":
                    return pdf
            time.sleep(0.5)
        raise RuntimeError("SIGIA no entregó un PDF dentro del tiempo esperado.")
    finally:
        driver.quit()


def extraer_productos(pdf_path: Path) -> list[dict[str, str]]:
    """Extrae filas tabulares del PDF sin interpretar vigencia ni recomendar dosis."""
    import pdfplumber

    products = []
    seen = set()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if len(row) != 12:
                        continue
                    cells = [" ".join((value or "").split()) for value in row]
                    registration, name, owner, ingredient, category, unit, dose_ha, dose_pct, dose, lmr, pc, notes = cells
                    if not registration or not name or "registro" in registration.lower():
                        continue
                    key = (registration, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    products.append({
                        "registration": registration, "name": name, "owner": owner,
                        "ingredient": ingredient, "category": category, "unit": unit,
                        "dose_ha": dose_ha, "dose_pct": dose_pct, "dose": dose,
                        "lmr": lmr, "pc": pc, "notes": notes,
                    })
    return products
