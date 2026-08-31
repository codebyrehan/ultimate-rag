"""Test fixtures: generates a sample multi-page PDF in-memory for ingestion tests."""

from __future__ import annotations

import io
from pathlib import Path

import fitz  # pymupdf

SAMPLE_TEXT = """
EMPLOYEE HANDBOOK

1. Purpose
This handbook defines the company policy for all employees.

2. Leave Policy
Full-time employees accrue 20 days of annual leave per year.
Managers accrue 25 days of annual leave per year.
Unused leave rolls over for up to one year.

3. Code of Conduct
Employees must act with integrity and respect.
All employees sign the code of conduct annually.

4. Remote Work Policy
Remote work is permitted up to three days per week.
Managers may approve additional remote days at their discretion.

Confidential: internal use only.
"""


def make_sample_pdf(path: Path | None = None, pages: int = 2) -> bytes:
    """Return bytes of a multi-page PDF with deterministic content."""
    doc = fitz.open()
    for p in range(pages):
        page = doc.new_page(width=595, height=842)  # A4
        text = SAMPLE_TEXT if p == 0 else SAMPLE_TEXT + f"\nAppendix page {p + 1}.\n"
        page.insert_text((72, 72), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    data = buf.getvalue()
    doc.close()
    if path is not None:
        path.write_bytes(data)
    return data


def make_typed_pdf(path: Path, text_per_page: list[str]) -> Path:
    """Create a PDF where each page has the given text."""
    doc = fitz.open()
    for text in text_per_page:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(str(path))
    doc.close()
    return path
