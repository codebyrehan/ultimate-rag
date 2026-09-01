"""Text + table extraction from PDFs using PyMuPDF.

Returns per-page text with header/footer blocks stripped (configurable by
vertical margin). Pages with insufficient text are flagged so the OCR
provider can be applied downstream.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import fitz  # pymupdf

from ultimate_rag.core.config import Settings

logger = logging.getLogger("ultimate_rag.ingestion.extractor")

# Minimum ratio of non-whitespace characters per page to consider it "text-rich".
_SCANNED_TEXT_RATIO = 0.01


@dataclass
class Table:
    """A detected table as markdown-ish structured data."""

    page_number: int
    rows: list[list[str]] = field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class PageText:
    page_number: int
    text: str
    is_scanned: bool
    char_count: int


@dataclass
class ExtractedDocument:
    file_path: str
    page_count: int
    pages: list[PageText] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    title: str | None = None

    @property
    def all_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


def _strip_headers_footers(page: fitz.Page, text: str, strip: bool = True) -> str:
    """Remove header/footer blocks based on vertical position."""
    if not strip or not text:
        return text
    rect = page.rect
    header_cutoff = rect.height * 0.10
    footer_cutoff = rect.height * 0.90
    blocks = page.get_text("blocks")
    kept = []
    for b in blocks:
        # block bbox: x0, y0, x1, y1, "text", block_no, block_type
        y0 = b[1]
        y1 = b[3]
        if y1 <= header_cutoff or y0 >= footer_cutoff:
            continue  # header/footer
        kept.append(b[4])
    if kept:
        return "\n".join(kept)
    return text


async def extract_document(file_path: str, settings: Settings) -> ExtractedDocument:
    """Extract text + tables from a PDF (CPU-bound work in a worker thread)."""

    def _work() -> ExtractedDocument:
        doc = fitz.open(file_path)
        try:
            pages: list[PageText] = []
            tables: list[Table] = []
            for i, page in enumerate(doc, start=1):
                text = page.get_text() or ""
                stripped = _strip_headers_footers(page, text)
                char_count = len(stripped.replace(" ", "").replace("\n", ""))
                is_scanned = char_count < max(1, int(page.rect.width * page.rect.height * 0.0001))
                ratio = char_count / max(1, (page.rect.width * page.rect.height))
                if ratio < _SCANNED_TEXT_RATIO and char_count < 50:
                    is_scanned = True
                pages.append(
                    PageText(page_number=i, text=stripped, is_scanned=is_scanned, char_count=char_count)
                )

                if settings.tables_enabled:
                    for tbl in page.find_tables():
                        rows: list[list[str]] = []
                        try:
                            extracted = tbl.extract()
                            if extracted:
                                rows = [list(r) for r in extracted]
                        except Exception:
                            rows = []
                        tables.append(
                            Table(
                                page_number=i,
                                rows=rows,
                                bbox=tbl.bbox,
                            )
                        )
            title = doc.metadata.get("title") if doc.metadata else None
            return ExtractedDocument(
                file_path=file_path,
                page_count=len(pages),
                pages=pages,
                tables=tables,
                title=title,
            )
        finally:
            doc.close()

    return await asyncio.to_thread(_work)
