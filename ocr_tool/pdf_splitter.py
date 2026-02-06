from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from .models import PageImage
from .utils.paths import ensure_dir


def split_pdf_to_images(pdf_path: Path, out_dir: Path, dpi: int) -> list[PageImage]:
    """Render PDF pages to PNG images in strict page order (1..N)."""

    ensure_dir(out_dir)

    doc = fitz.open(pdf_path)
    pages: list[PageImage] = []

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for idx in range(doc.page_count):
        page_id = idx + 1
        page = doc.load_page(idx)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        image_path = out_dir / f"{page_id:04d}.png"
        pix.save(str(image_path))

        with Image.open(image_path) as im:
            width, height = im.size

        pages.append(
            PageImage(
                page_id=page_id,
                image_path=str(image_path),
                width=width,
                height=height,
            )
        )

    return pages
