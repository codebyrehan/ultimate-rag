"""OCR providers.

``TesseractOCR`` renders PDF pages to images (via PyMuPDF) and runs
``pytesseract``. If the Tesseract binary is missing, OCR degrades to a
no-op and a warning is logged (scanned pages fall back to empty text, which
keeps the pipeline running instead of crashing).

``NoOpOCR`` is used when ``OCR_ENABLED=false``.
"""

from __future__ import annotations

import asyncio
import io
import logging

import fitz  # pymupdf

from ultimate_rag.core.config import Settings

logger = logging.getLogger("ultimate_rag.ingestion.ocr")


class OCRProvider:
    async def ocr_page(self, file_path: str, page_number: int, lang: str) -> str:
        raise NotImplementedError

    def available(self) -> bool:
        raise NotImplementedError


class NoOpOCR(OCRProvider):
    """Always-available fallback: returns empty text, logs a notice."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def ocr_page(self, file_path: str, page_number: int, lang: str) -> str:
        return ""

    def available(self) -> bool:
        return True


class TesseractOCR(OCRProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lang = settings.ocr_lang
        self._available: bool | None = None

    def available(self) -> bool:
        if self._available is None:
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                self._available = True
            except Exception as e:
                logger.warning("Tesseract not available: %s", e)
                self._available = False
        return self._available

    async def ocr_page(self, file_path: str, page_number: int, lang: str) -> str:
        try:
            import pytesseract
        except ImportError:
            return ""

        def _render_and_ocr() -> str:
            doc = fitz.open(file_path)
            try:
                page = doc.load_page(page_number - 1)
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img = pix.tobytes("png")
                return pytesseract.image_to_string(
                    io.BytesIO(img),
                    lang=lang or self.lang,
                    config="--psm 6",
                )
            finally:
                doc.close()

        return await asyncio.to_thread(_render_and_ocr)
