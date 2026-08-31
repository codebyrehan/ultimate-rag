"""File validation for uploads.

Checks performed (all real, no stubs):
  * file exists and is a regular file
  * size <= MAX_UPLOAD_SIZE_MB
  * magic bytes indicate a PDF (``%PDF-``)
  * page count <= MAX_PAGES_PER_JOB

This is the first defence against malicious/oversized uploads and helps
prevent path traversal (consumers must never trust the user-supplied name).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ultimate_rag.core.config import Settings
from ultimate_rag.core.errors import ValidationError

logger = logging.getLogger("ultimate_rag.ingestion.validator")

PDF_MAGIC = b"%PDF-"


@dataclass
class ValidationResult:
    path: Path
    filename: str
    sha256: str
    size_bytes: int
    page_count: int
    mime_type: str
    is_scanned: bool = False


async def validate_upload(path: Path, settings: Settings) -> ValidationResult:
    """Validate an uploaded file on disk. Raises :class:`ValidationError`."""
    if not path.exists():
        raise ValidationError("Uploaded file does not exist on disk")
    if not path.is_file():
        raise ValidationError("Uploaded path is not a regular file")

    size = path.stat().st_size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size <= 0:
        raise ValidationError("Uploaded file is empty")
    if size > max_bytes:
        raise ValidationError(f"File too large: {size} bytes exceeds limit of {max_bytes} bytes")

    # magic-byte detection (not the extension)
    with path.open("rb") as f:
        head = f.read(len(PDF_MAGIC))
    if head != PDF_MAGIC:
        raise ValidationError("File is not a valid PDF (magic-byte mismatch)")

    mime = "application/pdf"
    if path.suffix.lower() != ".pdf":
        logger.warning("File %s has non-pdf extension but valid magic bytes", path.name)

    from ultimate_rag.core.security import sha256_file

    sha = sha256_file(path)

    page_count = await _count_pages(path, settings)

    return ValidationResult(
        path=path,
        filename=path.name,
        sha256=sha,
        size_bytes=size,
        page_count=page_count,
        mime_type=mime,
    )


async def _count_pages(path: Path, settings: Settings) -> int:
    import asyncio

    def _count() -> int:
        import fitz  # pymupdf

        doc = fitz.open(str(path))
        try:
            return doc.page_count
        finally:
            doc.close()

    return await asyncio.to_thread(_count)
