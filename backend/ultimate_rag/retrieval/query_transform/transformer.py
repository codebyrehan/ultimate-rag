"""Query transformation: rewrite + expansion.

Improves retrieval recall by normalising the user query before embedding and
BM25 lookup. Transformation is settings-driven and degrades gracefully:
- Query rewriting decomposes multi-part questions into a single canonical
  form (deterministic, regex/token based — no LLM required).
- Expansion generates semantically-related query variants used to gather
  extra candidates that are fused alongside the original.

Both strategies are deterministic so they are safe for CI/offline use; a real
deployment would swap in an LLM-based rewriter/expansor via the same interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class TransformedQuery:
    """Output of query transformation."""

    original: str
    rewritten: str
    expanded: list[str] = None  # type: ignore[assignment]
    multi_queries: list[str] = None  # type: ignore[assignment]
    hyde_answer: str | None = None

    def __post_init__(self) -> None:
        if self.expanded is None:
            self.expanded = []
        if self.multi_queries is None:
            self.multi_queries = []


class QueryRewriter:
    """Decompose multi-part questions into a canonical rewritten query.

    Strips conversational prefixes, lowercases, and joins the surviving
    content-bearing tokens back into a single normalised string.
    """

    _PREFIXES = re.compile(
        r"^\s*(can you|could you|pls|please|i want to know|i'd like to know|)"
        r"[\s,:-]*",
        re.IGNORECASE,
    )

    def rewrite(self, query: str) -> str:
        q = self._PREFIXES.sub("", query)
        tokens = _TOKEN_RE.findall(q.lower())
        return " ".join(tokens) if tokens else q.strip().lower()


class QueryExpander:
    """Generate deterministic query variants for recall.

    For each content token not already present, produces a variant that
    substitutes a synonym from a small deterministic set. This adds recall
    without requiring a thesaurus service.
    """

    _SYNONYMS: ClassVar[dict[str, list[str]]] = {
        "leave": ["vacation", "time off"],
        "policy": ["rule", "guideline", "procedure"],
        "salary": ["compensation", "pay"],
        "remote": ["telecommute", "work from home"],
    }

    def __init__(self, max_variants: int = 3) -> None:
        self.max_variants = max_variants

    def expand(self, query: str) -> list[str]:
        tokens = _TOKEN_RE.findall(query.lower())
        variants: list[str] = []
        for tok in tokens:
            syns = self._SYNONYMS.get(tok)
            if not syns:
                continue
            for syn in syns[: self.max_variants]:
                variant = query.replace(tok, syn, 1)
                variant = variant.strip()
                if variant and variant.lower() != query.lower() and variant not in variants:
                    variants.append(variant)
                if len(variants) >= self.max_variants:
                    return variants
        return variants


@dataclass
class QueryTransformConfig:
    """Thin wrapper over the relevant settings flags."""

    rewrite_enabled: bool
    expansion_enabled: bool
    hyde_enabled: bool
    multi_query: bool
    max_variants: int = 3

    @classmethod
    def from_settings(cls, settings) -> QueryTransformConfig:
        return cls(
            rewrite_enabled=getattr(settings, "query_rewrite_enabled", True),
            expansion_enabled=getattr(settings, "query_expansion_enabled", False),
            hyde_enabled=getattr(settings, "hyde_enabled", False),
            multi_query=getattr(settings, "multi_query_enabled", False),
            max_variants=getattr(settings, "query_expansion_max_variants", 3),
        )


class QueryTransformer:
    """Composes rewriting + expansion into a single transformation pass.

    The retrieval pipeline calls :meth:`transform` once per user query and
    stores the result on the :class:`RetrievalContext`; the rewritten query
    drives dense + BM25 retrieval while expansion variants gather additional
    candidates that are fused via RRF.
    """

    def __init__(self, config: QueryTransformConfig) -> None:
        self.config = config
        self.rewriter = QueryRewriter()
        self.expander = QueryExpander(config.max_variants) if config.expansion_enabled else StubExpander()
        self.multi_expander = MultiQueryExpander(config.max_variants)
        self.hyde_gen = HydeGenerator()

    def transform(self, query: str) -> TransformedQuery:
        rewritten = self.rewriter.rewrite(query) if self.config.rewrite_enabled else query
        expanded = self.expander.expand(rewritten) if self.config.expansion_enabled else []
        multi_queries = self.multi_expander.expand(rewritten) if self.config.multi_query else []
        hyde_answer = self.hyde_gen.generate(query, rewritten) if self.config.hyde_enabled else None
        return TransformedQuery(
            original=query,
            rewritten=rewritten,
            expanded=expanded,
            multi_queries=multi_queries,
            hyde_answer=hyde_answer,
        )


def build_query_transformer(settings) -> QueryTransformer:
    """Construct a :class:`QueryTransformer` from settings."""
    return QueryTransformer(QueryTransformConfig.from_settings(settings))


class MultiQueryExpander:
    """Generate paraphrased query variants for multi-query retrieval.

    Uses deterministic template-based rewriting and synonym substitution
    to produce alternative phrasings of the same question.  Each variant
    is independently used to gather dense + BM25 candidates that are later
    fused via RRF.
    """

    _TEMPLATES: ClassVar[list[str]] = [
        "{q}",
        "what is {q}",
        "tell me about {q}",
        "information on {q}",
        "explain {q}",
    ]

    _SYNONYMS: ClassVar[dict[str, list[str]]] = {
        "what": ["which", "how"],
        "policy": ["rules", "procedures", "guidelines"],
        "salary": ["compensation", "pay", "income"],
        "remote": ["telecommute", "work from home"],
        "document": ["file", "record", "report"],
        "leave": ["vacation", "time off", "holiday"],
    }

    def __init__(self, max_variants: int = 3) -> None:
        self.max_variants = max(max_variants, 1)

    def expand(self, query: str) -> list[str]:
        variants: list[str] = []
        seen: set[str] = set()
        tokens = _TOKEN_RE.findall(query.lower())
        for template in self._TEMPLATES:
            v = template.format(q=query).strip()
            v = re.sub(r"\s+", " ", v)
            if v.lower() not in seen and v.lower() != query.lower():
                seen.add(v.lower())
                variants.append(v)
            if len(variants) >= self.max_variants:
                break
        if len(variants) >= self.max_variants:
            return variants
        for tok in tokens:
            if len(variants) >= self.max_variants:
                return variants
            syns = self._SYNONYMS.get(tok)
            if not syns:
                continue
            for syn in syns:
                v = query.replace(tok, syn, 1)
                v = re.sub(r"\s+", " ", v).strip()
                if v.lower() not in seen and v.lower() != query.lower():
                    seen.add(v.lower())
                    variants.append(v)
                if len(variants) >= self.max_variants:
                    return variants
        return variants


class HydeGenerator:
    """Generate a hypothetical answer to the query for HyDE.

    Produces a short, deterministic one-sentence answer derived from
    the query itself.  The embedding of this answer is used as the dense
    query vector, which often improves retrieval for factoid queries.
    """

    _PREFIXES = re.compile(
        r"^\s*(can you|could you|pls|please|i want to know|i'd like to know|)"
        r"[\s,:-]*",
        re.IGNORECASE | re.IGNORECASE,
    )

    def generate(self, query: str, rewritten: str) -> str:
        q = self._PREFIXES.sub("", query)
        tokens = _TOKEN_RE.findall(q.lower())
        if tokens:
            head = tokens[0].capitalize()
            rest = " ".join(tokens[1:]) if len(tokens) > 1 else rewritten
        else:
            head = rewritten.capitalize()
            rest = ""
        return f"{head} {rest}." if rest else f"{head}."


class StubExpander(QueryExpander):
    """No-op expander that returns only the original query."""

    def expand(self, query: str) -> list[str]:
        return []
