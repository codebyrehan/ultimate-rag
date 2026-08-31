"""Semantic chunker with parent/child chunk generation.

Chunks on sentence + heading boundaries (not naive fixed-length) with
configurable overlap, then groups child chunks into larger parent chunks
by section. Each segment carries metadata needed for citation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ultimate_rag.core.config import Settings
from ultimate_rag.core.ids import new_id

logger = logging.getLogger("ultimate_rag.ingestion.chunker")

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
_HEADING_RE = re.compile(r"^[A-Z0-9][A-Za-z0-9 ,.:/\-&'']{1,70}$")


def _token_count(text: str) -> int:
    """Rough token estimate (4 chars/tok). Cheap and provider-agnostic."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _is_heading(line: str) -> bool:
    """Heuristic: short, no trailing terminal punctuation, title-like."""
    stripped = line.strip()
    if len(stripped) > 80 or len(stripped) < 2:
        return False
    if stripped[-1] in ".:;":
        return False
    words = stripped.split()
    if words and all(w[0].isupper() for w in words if w):
        return bool(_HEADING_RE.match(stripped))
    return False


@dataclass
class ChunkSegment:
    text: str
    token_count: int
    page_number: int
    section: str | None = None
    subsection: str | None = None
    chunk_type: str = "child"
    parent_id: str | None = None
    chunk_id: str = field(default_factory=new_id)
    metadata: dict | None = None


class SemanticChunker:
    """Splits extracted page text into semantic child chunks then parents."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        self.parent_size = settings.parent_chunk_size
        self.sentence_threshold = settings.chunk_sentence_thresh

    def chunk_page(self, page_text: str, page_number: int) -> list[ChunkSegment]:
        """Produce child chunks for a single page, tracking heading context."""
        if not page_text or not page_text.strip():
            return []

        lines = [ln.strip() for ln in page_text.splitlines()]
        current_section: str | None = None
        current_subsection: str | None = None
        chunks: list[ChunkSegment] = []
        buffer: list[str] = []
        buf_chars = 0

        def flush(keep_tail: bool = False) -> None:
            nonlocal buffer, buf_chars
            if not buffer:
                return
            text = " ".join(buffer).strip()
            if text:
                chunks.append(
                    ChunkSegment(
                        text=text,
                        token_count=_token_count(text),
                        page_number=page_number,
                        section=current_section,
                        subsection=current_subsection,
                    )
                )
            if keep_tail and buffer:
                buffer = [buffer[-1]]
                buf_chars = len(buffer[-1])
            else:
                buffer = []
                buf_chars = 0

        def add_line(line: str) -> None:
            nonlocal buffer, buf_chars, current_section, current_subsection
            if _is_heading(line):
                flush(keep_tail=False)
                current_subsection = current_section
                current_section = line
                return
            if not buffer:
                buffer = [line]
            else:
                if buf_chars + 1 + len(line) >= self.chunk_size:
                    flush(keep_tail=True)
                buffer.append(line)
            buf_chars = sum(len(b) for b in buffer)

        for raw in lines:
            if not raw:
                if buffer and buf_chars >= self.chunk_size * 0.5:
                    flush(keep_tail=True)
                continue
            add_line(raw)
        flush(keep_tail=False)

        final: list[ChunkSegment] = []
        for ch in chunks:
            if len(ch.text) <= self.chunk_size:
                final.append(ch)
            else:
                final.extend(self._split_large(ch))
        return final

    def _split_large(self, seg: ChunkSegment) -> list[ChunkSegment]:
        """Split an oversized segment into sentence-based chunks with overlap."""
        sentences = [s.strip() for s in _SENT_SPLIT.split(seg.text) if s and s.strip()]
        if not sentences:
            return [seg]
        out: list[ChunkSegment] = []
        buf: list[str] = []
        buf_chars = 0
        for sent in sentences:
            if buf and buf_chars + len(sent) + 1 >= self.chunk_size:
                text = " ".join(buf).strip()
                out.append(_copy(seg, text))
                overlap = buf[-1] if self.chunk_overlap > 0 else ""
                buf = [overlap] if overlap else []
                buf_chars = len(overlap) if overlap else 0
            buf.append(sent)
            buf_chars += len(sent) + 1
        if buf:
            text = " ".join(buf).strip()
            out.append(_copy(seg, text))
        return out

    def chunk_pages(self, pages: list[str]) -> list[ChunkSegment]:
        """Chunk every page, returning child segments with sequential page numbers."""
        children: list[ChunkSegment] = []
        for i, page_text in enumerate(pages, start=1):
            children.extend(self.chunk_page(page_text, i))
        return children

    def make_parents(self, children: list[ChunkSegment]) -> list[ChunkSegment]:
        """Group child chunks into parent chunks (by section, respecting parent size).

        Assigns ``parent_id`` on each child. Returns the list of parent segments.
        """
        parents: list[ChunkSegment] = []
        groups: list[list[ChunkSegment]] = []
        current: list[ChunkSegment] = []
        current_section: str | None = None

        for child in children:
            sec = child.section
            if current and (
                sec != current_section or _group_size(current) + len(child.text) > self.parent_size
            ):
                groups.append(current)
                current = []
            current.append(child)
            current_section = sec
        if current:
            groups.append(current)

        for group in groups:
            parent_id = new_id()
            parent_text = " ".join(c.text for c in group)
            parent = ChunkSegment(
                text=parent_text,
                token_count=_token_count(parent_text),
                page_number=group[0].page_number,
                section=group[0].section,
                subsection=group[0].subsection,
                chunk_type="parent",
                parent_id=None,
                chunk_id=parent_id,
            )
            parents.append(parent)
            for child in group:
                child.parent_id = parent_id
        return parents

    def chunk_document(self, pages: list[str]) -> list[ChunkSegment]:
        """End-to-end: chunk pages → build parents → return children + parents."""
        children = self.chunk_pages(pages)
        parents = self.make_parents(children)
        return children + parents


def _copy(seg: ChunkSegment, text: str) -> ChunkSegment:
    return ChunkSegment(
        text=text,
        token_count=_token_count(text),
        page_number=seg.page_number,
        section=seg.section,
        subsection=seg.subsection,
        chunk_type=seg.chunk_type,
        parent_id=seg.parent_id,
        metadata=seg.metadata,
    )


def _group_size(group: list[ChunkSegment]) -> int:
    return sum(len(c.text) for c in group)
