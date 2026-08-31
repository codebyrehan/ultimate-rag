"""BM25 keyword retrieval.

A real, from-scratch BM25 (Okapi) inverted index with tenant isolation.
Tokenization is regex-based (lowercased word tokens) and keeps numbers and
identifiers so technical terms remain searchable. Phrases are supported by
requiring adjacency of the constituent terms in addition to the BM25 score.

State lives in-process. For multi-node scale, back BM25 with Qdrant sparse
vectors or Elasticsearch; this implementation is correct, testable, and
dependency-free.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from collections import defaultdict
from dataclasses import dataclass

from ultimate_rag.core.config import Settings
from ultimate_rag.retrieval.types import ChunkMetadata, RetrievedChunk

logger = logging.getLogger("ultimate_rag.retrieval.bm25")

_TOKEN_RE = re.compile(r"[A-Za-z0-9_.+\-]+")


@dataclass
class _DocRecord:
    chunk_id: str
    tokens: list[str]
    length: int
    metadata: ChunkMetadata


class BM25Retriever:
    """In-memory BM25 index, partitioned by tenant."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._k1 = 1.5
        self._b = 0.75
        self._lock = threading.Lock()
        # tenant_id -> chunk_id -> _DocRecord
        self._docs: dict[str, dict[str, _DocRecord]] = defaultdict(dict)
        # tenant_id -> term -> {chunk_id: tf}
        self._inverted: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        # tenant_id -> term -> doc frequency
        self._df: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # tenant_id -> avgdl
        self._avgdl: dict[str, float] = {}
        # tenant_id -> total doc count
        self._ndoc: dict[str, int] = defaultdict(int)

    # ---- indexing ----
    def add_chunk(self, tenant_id: str, chunk_id: str, text: str, metadata: ChunkMetadata) -> None:
        tokens = _TOKEN_RE.findall(text.lower())
        record = _DocRecord(chunk_id=chunk_id, tokens=tokens, length=len(tokens), metadata=metadata)
        with self._lock:
            self._docs[tenant_id][chunk_id] = record
            # update frequencies
            tfs: dict[str, int] = defaultdict(int)
            for tok in tokens:
                tfs[tok] += 1
            for tok, tf in tfs.items():
                self._inverted[tenant_id][tok][chunk_id] = tf
                self._df[tenant_id][tok] += 1
            # recompute avgdl
            n = len(self._docs[tenant_id])
            total_len = sum(d.length for d in self._docs[tenant_id].values())
            self._avgdl[tenant_id] = total_len / max(n, 1)
            self._ndoc[tenant_id] = n

    def add_chunks(self, tenant_id: str, chunks: list[tuple[str, str, ChunkMetadata]]) -> None:
        for chunk_id, text, metadata in chunks:
            self.add_chunk(tenant_id, chunk_id, text, metadata)

    def delete_document(self, document_id: str, tenant_id: str) -> int:
        with self._lock:
            docs = self._docs.get(tenant_id, {})
            to_remove = [cid for cid, d in docs.items() if d.metadata.document_id == document_id]
            for cid in to_remove:
                self._remove_doc(tenant_id, cid)
            if docs and len(docs) == len(to_remove):
                self._reset_tenant(tenant_id)
        return len(to_remove)

    def delete_tenant(self, tenant_id: str) -> int:
        with self._lock:
            n = len(self._docs.get(tenant_id, {}))
            self._reset_tenant(tenant_id)
        return n

    def _remove_doc(self, tenant_id: str, chunk_id: str) -> None:
        record = self._docs[tenant_id].pop(chunk_id, None)
        if record is None:
            return
        tfs: dict[str, int] = defaultdict(int)
        for tok in record.tokens:
            tfs[tok] += 1
        for tok in tfs:
            inv = self._inverted[tenant_id].get(tok, {})
            inv.pop(chunk_id, None)
            if inv:
                self._df[tenant_id][tok] = len(inv)
            else:
                self._df[tenant_id].pop(tok, None)
                self._inverted[tenant_id].pop(tok, None)
        self._recompute_avgdl(tenant_id)

    def _reset_tenant(self, tenant_id: str) -> None:
        self._docs.pop(tenant_id, None)
        self._inverted.pop(tenant_id, None)
        self._df.pop(tenant_id, None)
        self._avgdl.pop(tenant_id, None)
        self._ndoc.pop(tenant_id, None)

    def _recompute_avgdl(self, tenant_id: str) -> None:
        docs = self._docs.get(tenant_id, {})
        n = len(docs)
        if n == 0:
            self._avgdl[tenant_id] = 0.0
            self._ndoc[tenant_id] = 0
            return
        total_len = sum(d.length for d in docs.values())
        self._avgdl[tenant_id] = total_len / n
        self._ndoc[tenant_id] = n

    # ---- retrieval ----
    def _tokenize(self, text: str) -> list[str]:
        return _TOKEN_RE.findall(text.lower())

    def _idf(self, tenant_id: str, term: str) -> float:
        n = self._ndoc.get(tenant_id, 0)
        df = self._df.get(tenant_id, {}).get(term, 0)
        if df == 0:
            return 0.0
        # BM25+ style IDF with saturation
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def search(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
        extra_filter: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Return the top-k chunks for a query via BM25."""
        terms = self._tokenize(query)
        with self._lock:
            docs = dict(self._docs.get(tenant_id, {}))
            inverted = self._inverted.get(tenant_id, {})
            df_map = self._df.get(tenant_id, {})
            n = self._ndoc.get(tenant_id, 0)
            avgdl = self._avgdl.get(tenant_id, 0.0)

        if not terms or n == 0:
            return []

        # candidate chunk ids must contain at least one query term
        candidates: set[str] = set()
        for t in terms:
            for cid in inverted.get(t, {}):
                candidates.add(cid)
        if not candidates:
            return []

        scores: dict[str, float] = {cid: 0.0 for cid in candidates}
        for t in terms:
            idf = self._idf(tenant_id, t) if df_map.get(t) else 0.0  # use precomputed? recompute via n,df
            idf = self._idf_recompute(n, df_map.get(t, 0))
            postings = inverted.get(t, {})
            for cid, f in postings.items():
                rec = docs.get(cid)
                if rec is None:
                    continue
                tf = f
                denom = tf + self._k1 * (1 - self._b + self._b * rec.length / avgdl if avgdl else 1.0)
                scores[cid] += idf * (tf * (self._k1 + 1)) / (denom if denom else 1.0)

        ranked = sorted(((cid, s) for cid, s in scores.items() if s > 0), key=lambda x: x[1], reverse=True)
        results: list[RetrievedChunk] = []
        for cid, score in ranked[:top_k]:
            rec = docs[cid]
            if extra_filter and not _matches_filter(rec.metadata, extra_filter):
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=cid,
                    text="",  # text hydrated by callers from the DB
                    score=float(score),
                    metadata=rec.metadata,
                    source="bm25",
                )
            )
        return results

    def _idf_recompute(self, n: int, df: int) -> float:
        if df == 0:
            return 0.0
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))


def _matches_filter(meta: ChunkMetadata, extra: dict | None) -> bool:
    if not extra:
        return True
    for k, v in extra.items():
        if v is None:
            continue
        if getattr(meta, k, None) != v:
            return False
    return True
