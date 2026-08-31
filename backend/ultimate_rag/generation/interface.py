"""Generation layer: LLM provider abstraction and answer synthesis.

Defines the provider interface used by all concrete LLM backends (Ollama,
OpenAI, HuggingFace, stub). The answer builder takes a
:class:`ultimate_rag.retrieval.types.RetrievalContext` and an LLM provider,
synthesises a grounded answer, and attaches citations back to the retrieved
chunks.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import dataclass, field

from ultimate_rag.core.config import Settings

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, accurate assistant. Answer the user's question using "
    "only the provided context. If you cannot answer from the context, say so. "
    "Cite sources inline as [N]."
)


@dataclass
class Citation:
    """A reference to a retrieved chunk used as evidence for an answer."""

    chunk_id: str
    label: str
    score: float
    doc_filename: str
    page_number: int

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "label": self.label,
            "score": self.score,
            "doc_filename": self.doc_filename,
            "page_number": self.page_number,
        }


@dataclass
class LLMResponse:
    """Raw response from an LLM provider."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


class LLMProvider(abc.ABC):
    """Async LLM provider interface.

    Implementations are settings-driven and may be cached for the process
    lifetime when expensive to construct (e.g. local HF weights).
    """

    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abc.abstractmethod
    async def generate(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate a completion from a list of ``{"role": ..., "content": ...}`` messages."""
        ...

    async def stream(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """Async generator yielding text deltas.

        Default implementation falls back to :meth:`generate` and emits the
        whole response as a single chunk so non-streaming providers work with
        the streaming API.
        """
        resp = await self.generate(messages, temperature=temperature, max_tokens=max_tokens)
        yield resp.text

    async def aclose(self) -> None:
        """Release resources held by the provider."""
        return None


def citation_for(chunk) -> Citation:
    """Build a :class:`Citation` from a :class:`RetrievedChunk`."""
    label = chunk.citation_label
    return Citation(
        chunk_id=chunk.chunk_id,
        label=label,
        score=chunk.score,
        doc_filename=chunk.metadata.doc_filename,
        page_number=chunk.metadata.page_number,
    )


@dataclass
class Answer:
    """A grounded answer with supporting citations."""

    text: str
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    model: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "citations": [c.to_dict() for c in self.citations],
            "confidence": round(self.confidence, 4),
            "model": self.model,
        }


@dataclass
class SourcePassage:
    """A single context passage sent to the LLM."""

    index: int
    text: str
    citation: Citation
