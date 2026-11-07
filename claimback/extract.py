"""Turn an uploaded denial letter (PDF, image or text) into plain text."""
from __future__ import annotations

import io
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def text_from_bytes(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _pdf_text(data)
    if ext in IMAGE_EXTS:
        return _ocr_image(data)
    return data.decode("utf-8", errors="ignore")


def text_from_path(path: str | Path) -> str:
    path = Path(path)
    return text_from_bytes(path.read_bytes(), path.name)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if len(text.strip()) > 50:
        return text
    # Scanned PDF with no text layer: rasterize and OCR each page.
    try:
        import pypdfium2 as pdfium  # optional dependency
    except ImportError:
        return text
    pdf = pdfium.PdfDocument(data)
    pages = []
    for page in pdf:
        img = page.render(scale=2).to_pil()
        pages.append(_ocr_pil(img))
    return "\n".join(pages)


def _ocr_image(data: bytes) -> str:
    from PIL import Image

    return _ocr_pil(Image.open(io.BytesIO(data)))


def _ocr_pil(img) -> str:
    import pytesseract

    return pytesseract.image_to_string(img.convert("L"))
