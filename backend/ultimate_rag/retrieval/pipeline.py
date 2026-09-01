"""Retrieval pipeline orchestration.

Hybrid retrieval: dense embeddings + BM25 keyword search -> weighted RRF
fusion -> deduplication -> cross-encoder reranking -> context compression.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import TYPE_CHECKING

from ultimate_rag.core.config import Settings
from ultimate_rag.core.metrics import measure
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.compression import compress
from ultimate_rag.retrieval.dedup import dedup_chunks
from ultimate_rag.retrieval.dense import DenseRetriever
from ultimate_rag.retrieval.fusion import RRFusioner
from ultimate_rag.retrieval.query_transform.transformer import build_query_transformer
from ultimate_rag.retrieval.reranker import Reranker
from ultimate_rag.retrieval.types import RetrievalContext, RetrievedChunk
from ultimate_rag.vecstore.interface import VectorStore

if TYPE_CHECKING:
    from ultimate_rag.embeddings.interface import EmbeddingProvider

logger = logging.getLogger("ultimate_rag.retrieval.pipeline")


def _query_cache_key(query: str, model: str, dim: int) -> str:
    return f"{model}:{dim}:{query}"


class RetrievalPipeline:
    """Orchestrates hybrid retrieval across dense and lexical search."""

    def __init__(
        self,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        bm25: BM25Retriever,
        reranker: Reranker,
        settings: Settings,
    ) -> None:
        self.dense = DenseRetriever(embeddings, vector_store, settings)
        self.bm25 = bm25
        self.reranker = reranker
        self.settings = settings
        self.transformer = build_query_transformer(settings)
        self._query_embedding_cache: dict[str, tuple[list[float], str]] = {}
        self._query_cache_model = settings.embedding_model
        self._query_cache_dim = settings.embedding_dim

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        text_loader: Callable[[list[str]], Awaitable[dict[str, str]]] | None = None,
    ) -> RetrievalContext:
        ctx = RetrievalContext(tenant_id=tenant_id, query=query)
        t_total = time.perf_counter()

        with measure("retrieval.total_latency_ms"):
            t0 = time.perf_counter()
            tq = self.transformer.transform(query)
            ctx.rewritten_query = tq.rewritten
            ctx.expanded_queries = tq.expanded
            ctx.multi_queries = tq.multi_queries
            ctx.hyde_answer = tq.hyde_answer
            ctx.stage_timings["query_transform_ms"] = (time.perf_counter() - t0) * 1000

            search_query = tq.rewritten
            dense_top = self.settings.dense_top_k if self.settings.dense_retrieval_enabled else 0

            t0 = time.perf_counter()
            dense_task = None
            if dense_top:
                cache_key = _query_cache_key(search_query, self._query_cache_model, self._query_cache_dim)
                cached_vec = self._query_embedding_cache.get(cache_key)
                if cached_vec is not None:
                    dense_task = self.dense.retrieve_with_vector(cached_vec[0], tenant_id, dense_top)
                else:
                    if tq.hyde_answer:
                        with measure("retrieval.hyde_embed_ms"):
                            hyde_vec = await self.dense.embeddings.aembed([tq.hyde_answer])
                        dense_task = self.dense.retrieve_with_vector(
                            hyde_vec[0].tolist(), tenant_id, dense_top
                        )
                    else:
                        qe = await self.dense.embeddings.aembed([search_query])
                        vec = qe[0].tolist()
                        self._query_embedding_cache[cache_key] = (vec, tenant_id)
                        dense_task = self.dense.retrieve_with_vector(vec, tenant_id, dense_top)

            bm25_top = self.settings.bm25_top_k
            bm25_task = (
                asyncio.to_thread(self.bm25.search, search_query, tenant_id, bm25_top)
                if bm25_top
                else None
            )

            if dense_task and bm25_task:
                dense_results, bm25_results = await asyncio.gather(
                    dense_task, bm25_task, return_exceptions=True
                )
                if isinstance(dense_results, Exception):
                    logger.warning("Dense retrieval failed: %s", dense_results)
                    dense_results = []
                if isinstance(bm25_results, Exception):
                    logger.warning("BM25 retrieval failed: %s", bm25_results)
                    bm25_results = []
                ctx.dense_candidates.extend(dense_results)
                ctx.bm25_candidates = bm25_results if isinstance(bm25_results, list) else []
            else:
                if dense_task:
                    ctx.dense_candidates.extend(await dense_task)
                if bm25_task:
                    ctx.bm25_candidates = await bm25_task
            ctx.stage_timings["retrieval_ms"] = (time.perf_counter() - t0) * 1000

            if tq.expanded:
                t0 = time.perf_counter()
                tasks = [
                    self.dense.retrieve(variant, tenant_id, max(1, dense_top // 2))
                    for variant in tq.expanded
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.warning("Expanded dense retrieval failed: %s", r)
                    else:
                        ctx.dense_candidates.extend(r)
                ctx.stage_timings["expansion_retrieval_ms"] = (time.perf_counter() - t0) * 1000

            if tq.multi_queries:
                t0 = time.perf_counter()
                tasks = []
                for mq in tq.multi_queries:
                    tasks.append(self.dense.retrieve(mq, tenant_id, dense_top))
                    if bm25_top:
                        tasks.append(asyncio.to_thread(self.bm25.search, mq, tenant_id, bm25_top))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        logger.warning("Multi-query retrieval failed: %s", r)
                    else:
                        if i % 2 == 0:
                            ctx.dense_candidates.extend(r)
                        else:
                            ctx.bm25_candidates.extend(r)
                ctx.stage_timings["multi_query_retrieval_ms"] = (time.perf_counter() - t0) * 1000

            with measure("retrieval.rrf_fusion_ms"):
                rrf = RRFusioner(
                    k=self.settings.rrf_k,
                    dense_weight=self.settings.dense_weight,
                    lexical_weight=self.settings.lexical_weight,
                )
                pre_rerank = rrf.fuse(
                    ctx.dense_candidates,
                    ctx.bm25_candidates,
                    top_k=self.settings.reranker_top_k * 2,
                )
            ctx.fused_candidates = pre_rerank

            deduped = dedup_chunks(pre_rerank)

            if text_loader is not None:
                t0 = time.perf_counter()
                await self._hydrate(deduped, text_loader)
                ctx.stage_timings["hydration_ms"] = (time.perf_counter() - t0) * 1000

            with measure("retrieval.rerank_latency_ms"):
                reranked = await self.reranker.rerank(query, deduped, top_k=self.settings.reranker_top_k)
            ctx.reranked = reranked

            ctx.compressed = compress(reranked, top_k=self.settings.final_top_k)

        ctx.stage_timings["total_ms"] = (time.perf_counter() - t_total) * 1000
        logger.info(
            "retrieval: dense=%d bm25=%d rerank=%d final=%d timings=%s",
            len(ctx.dense_candidates),
            len(ctx.bm25_candidates),
            len(reranked),
            len(ctx.compressed),
            ctx.stage_timings,
        )
        return ctx

    async def _hydrate(self, chunks: list[RetrievedChunk], text_loader: Callable) -> None:
        texts = await text_loader([c.chunk_id for c in chunks])
        for c in chunks:
            c.text = texts.get(c.chunk_id, c.text)


async def build_retrieval_pipeline(container) -> RetrievalPipeline:
    settings = container.settings
    return RetrievalPipeline(
        embeddings=container.get("embeddings"),
        vector_store=container.get("vector_store"),
        bm25=container.get("bm25"),
        reranker=container.get("reranker"),
        settings=settings,
    )
