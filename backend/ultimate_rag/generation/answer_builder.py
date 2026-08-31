"""Answer synthesis from a retrieval context.

The :class:`AnswerBuilder` takes a :class:`RetrievalContext` (the output of
the retrieval pipeline), builds a citation-aware prompt, calls an
:class:`LLMProvider`, and assembles an :class:`Answer` with citations that
point back to the source chunks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ultimate_rag.core.metrics import inc, measure
from ultimate_rag.generation.interface import Answer, Citation, LLMProvider, LLMResponse
from ultimate_rag.retrieval.types import RetrievalContext, RetrievedChunk

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, accurate RAG assistant. Answer the user's question "
    "using ONLY the provided context passages (numbered [1], [2], ...). "
    "If the answer is not in the context, say you cannot answer. "
    "Cite each statement with its source number, e.g. [1], [2]."
)

_CONTEXT_DELIM_START = "=== CONTEXT START ==="
_CONTEXT_DELIM_END = "=== CONTEXT END ==="


class AnswerBuilder:
    """Synthesise a grounded answer from a retrieval context."""

    def __init__(self, llm: LLMProvider, settings) -> None:
        self.llm = llm
        self.settings = settings

    def _build_prompt(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """Return messages: system with numbered context, then optional history, then current query."""
        lines: list[str] = [DEFAULT_SYSTEM_PROMPT, "", _CONTEXT_DELIM_START, "Context:"]
        for i, chunk in enumerate(chunks, start=1):
            text = (chunk.text or "").strip()
            lines.append(f"[{i}] {text}")
        lines.append(_CONTEXT_DELIM_END)
        system_content = "\n".join(lines)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_content},
        ]
        if history:
            messages.extend({"role": m.get("role", "user"), "content": m["content"]} for m in history)
        messages.append({"role": "user", "content": query})
        return messages

    async def build_answer(
        self,
        ctx: RetrievalContext,
        text_loader: Callable[[list[str]], Awaitable[dict[str, str]]] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> Answer:
        chunks = ctx.compressed
        if text_loader is not None and chunks:
            texts = await text_loader([c.chunk_id for c in chunks])
            hydrated = []
            for c in chunks:
                c.text = texts.get(c.chunk_id, c.text)
                hydrated.append(c)
            chunks = hydrated

        citations = [self._citation(c) for c in chunks]
        messages = self._build_prompt(ctx.query, chunks, history)
        with measure("generation.llm_latency_ms"):
            resp: LLMResponse = await self.llm.generate(
                messages,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )
        confidence = self._confidence(chunks, ctx.query)
        inc("answers_generated")
        return Answer(
            text=resp.text,
            citations=citations,
            confidence=confidence,
            model=resp.model,
        )

    async def build_answer_stream(
        self,
        ctx: RetrievalContext,
        text_loader: Callable[[list[str]], Awaitable[dict[str, str]]] | None = None,
        history: list[dict[str, str]] | None = None,
    ):
        """Yield answer text deltas, then a final metadata dict.

        Consumers receive ``{"type": "token", "data": "<delta>"}`` messages
        followed by a single ``{"type": "done", ...}`` message carrying the
        full Answer metadata (citations, confidence, model).
        """
        chunks = ctx.compressed
        if text_loader is not None and chunks:
            texts = await text_loader([c.chunk_id for c in chunks])
            hydrated = []
            for c in chunks:
                c.text = texts.get(c.chunk_id, c.text)
                hydrated.append(c)
            chunks = hydrated

        citations = [self._citation(c) for c in chunks]
        messages = self._build_prompt(ctx.query, chunks, history)

        with measure("generation.llm_latency_ms"):
            async for delta in self.llm.stream(
                messages,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            ):
                yield {"type": "token", "data": delta}

        confidence = self._confidence(chunks, ctx.query)
        inc("answers_streamed")
        yield {
            "type": "done",
            "citations": [c.to_dict() for c in citations],
            "confidence": round(confidence, 4),
            "model": self.llm.name,
        }

    @staticmethod
    def _citation(chunk: RetrievedChunk) -> Citation:
        return Citation(
            chunk_id=chunk.chunk_id,
            label=chunk.citation_label,
            score=chunk.score,
            doc_filename=chunk.metadata.doc_filename,
            page_number=chunk.metadata.page_number,
        )

    @staticmethod
    def _confidence(chunks: list[RetrievedChunk], query: str) -> float:
        """Confidence = max score among chunks that share query tokens with text."""
        if not chunks:
            return 0.0
        max_score = max(c.score for c in chunks)
        return round(float(max_score), 4)
