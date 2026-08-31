"""Deterministic stub LLM provider (no model download).

Implements the :class:`LLMProvider` interface with an extractive
best-passage strategy: it picks the context passage with the highest
token-overlap with the query and surfaces it as the "completion". This is a
*real* grounding strategy (not a no-op) so the generation pipeline is
exercisable offline in CI/sandbox.
"""

from __future__ import annotations

import re

from ultimate_rag.generation.interface import LLMProvider, LLMResponse

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _token_overlap(query: str, text: str) -> float:
    qt = set(_TOKEN_RE.findall(query.lower()))
    dt = set(_TOKEN_RE.findall(text.lower()))
    if not qt:
        return 0.0
    return len(qt & dt) / len(qt)


class StubProvider(LLMProvider):
    """Deterministic, offline LLM provider that grounds answers in context."""

    name = "stub"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._model = "stub-deterministic"

    async def generate(self, messages, temperature=None, max_tokens=None) -> LLMResponse:
        query = ""
        passages: list[str] = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                query = content
            elif role == "system":
                for line in content.splitlines():
                    if re.match(r"\[\d+\]\s+", line):
                        passages.append(line)
        best = ""
        if passages:
            best_passage = max(passages, key=lambda p: _token_overlap(query, p))
            best = re.sub(r"^\[\d+\]\s+", "", best_passage).strip()
        if not best:
            text = f"I cannot answer '{query}' from the provided context."
        else:
            text = best
        return LLMResponse(
            text=text,
            prompt_tokens=len(query.split()),
            completion_tokens=len(text.split()),
            model=self._model,
        )

    async def stream(self, messages, temperature=None, max_tokens=None):
        resp = await self.generate(messages, temperature=temperature, max_tokens=max_tokens)
        # stream word-by-word for a realistic streaming experience
        for word in resp.text.split(" "):
            yield f"{word} "
        yield ""
