"""Extractor y procesador de imágenes para reportes fitosanitarios en PDF."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import List

from PIL import Image, ImageOps, UnidentifiedImageError
import pypdf

MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB
MIN_IMAGE_SIDE = 48
MAX_IMAGES_PER_REPORT = 36


def extract_images_from_pdf(
    pdf_bytes: bytes,
    max_images: int = MAX_IMAGES_PER_REPORT,
    min_side: int = MIN_IMAGE_SIDE,
) -> List[Image.Image]:
    """Extrae las imágenes incrustadas de un reporte PDF digital.

    Diseñado para reportes generados desde LibreOffice, Microsoft Word u otras herramientas
    de diagnóstico fitosanitario.
    """
    if not pdf_bytes:
        raise ValueError("El archivo PDF está vacío.")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError("El archivo PDF supera el tamaño máximo permitido (25 MB).")

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:
        raise ValueError("El archivo no es un documento PDF válido.") from exc

    if not reader.pages:
        raise ValueError("El documento PDF no contiene páginas.")

    extracted_images: List[Image.Image] = []

    for page_index, page in enumerate(reader.pages):
        try:
            page_images = page.images
        except Exception:
            continue

        for img_file in page_images:
            try:
                raw_data = img_file.data
                img = Image.open(io.BytesIO(raw_data))
                img = ImageOps.exif_transpose(img).convert("RGB")
            except (UnidentifiedImageError, OSError, ValueError):
                continue

            # Descartar elementos ornamentales, iconos o banners muy estrechos
            if img.width < min_side or img.height < min_side:
                continue

            extracted_images.append(img)
            if len(extracted_images) >= max_images:
                break
        if len(extracted_images) >= max_images:
            break

    if not extracted_images:
        raise ValueError(
            "No se encontraron fotografías válidas en el documento PDF. "
            "Asegúrate de incluir las imágenes de las plantas dentro del reporte."
        )

    return extracted_images


def image_to_base64_data_url(image: Image.Image, max_side: int = 700, quality: int = 82) -> str:
    """Convierte una imagen PIL a un Data URL JPEG optimizado para el navegador."""
    thumb = image.copy()
    thumb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"
