"""Normalise an uploaded document into:
- A primary PIL image (first page) for vision-LLM extraction
- Optional raw text (only available for native, non-scanned PDFs) for cross-checking

We deliberately use only the first page for extraction. Medical documents in this
service (referral letters, MCs, receipts) are typically single-page; processing
multiple pages would multiply cost without meaningful gain.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import fitz  # PyMuPDF
from PIL import Image

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


SUPPORTED_IMAGE_MIME = {"image/jpeg", "image/jpg", "image/png"}
SUPPORTED_PDF_MIME = {"application/pdf"}
SUPPORTED_MIME = SUPPORTED_IMAGE_MIME | SUPPORTED_PDF_MIME


class UnsupportedMimeError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


@dataclass
class NormalisedDocument:
    image: Image.Image
    raw_text: str  # empty string if not available
    is_native_pdf: bool
    page_count: int


def normalise(file_bytes: bytes, content_type: str) -> NormalisedDocument:
    if len(file_bytes) > settings.max_file_size_bytes:
        raise FileTooLargeError(
            f"File exceeds {settings.max_file_size_mb} MB limit"
        )

    ct = (content_type or "").lower()
    if ct in SUPPORTED_IMAGE_MIME:
        return _from_image_bytes(file_bytes)
    if ct in SUPPORTED_PDF_MIME:
        return _from_pdf_bytes(file_bytes)
    raise UnsupportedMimeError(f"Unsupported MIME type: {content_type}")


def _from_image_bytes(file_bytes: bytes) -> NormalisedDocument:
    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    return NormalisedDocument(
        image=image,
        raw_text="",
        is_native_pdf=False,
        page_count=1,
    )


def _from_pdf_bytes(file_bytes: bytes) -> NormalisedDocument:
    """Render the first page to a PIL image and pull embedded text if present."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        page_count = doc.page_count
        if page_count == 0:
            raise UnsupportedMimeError("PDF contains no pages")
        if page_count > settings.max_pdf_pages:
            logger.warning(
                "PDF has %d pages, processing first page only", page_count
            )

        first = doc.load_page(0)
        # 72 DPI is the PDF default; scale by target/72.
        zoom = settings.pdf_render_dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = first.get_pixmap(matrix=matrix, alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

        # Pull embedded text from all pages (cheap, useful for cross-check even
        # if extraction only sees page 1 — provider info often spans pages).
        raw_text_parts: list[str] = []
        for i in range(page_count):
            raw_text_parts.append(doc.load_page(i).get_text("text"))
        raw_text = "\n".join(raw_text_parts).strip()
        is_native = bool(raw_text)

        return NormalisedDocument(
            image=image,
            raw_text=raw_text,
            is_native_pdf=is_native,
            page_count=page_count,
        )
    finally:
        doc.close()
