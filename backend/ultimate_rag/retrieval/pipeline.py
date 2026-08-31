"""Retrieval pipeline orchestration.

Hybrid retrieval: dense embeddings + BM25 keyword search -> weighted RRF
fusion -> deduplication -> cross-encoder reranking -> context compression.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
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

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        text_loader: Callable[[list[str]], Awaitable[dict[str, str]]] | None = None,
    ) -> RetrievalContext:
        ctx = RetrievalContext(tenant_id=tenant_id, query=query)

        with measure("retrieval.total_latency_ms"):
            tq = self.transformer.transform(query)
            ctx.rewritten_query = tq.rewritten
            ctx.expanded_queries = tq.expanded
            ctx.multi_queries = tq.multi_queries
            ctx.hyde_answer = tq.hyde_answer
            search_query = tq.rewritten

            dense_top = self.settings.dense_top_k if self.settings.dense_retrieval_enabled else 0

            if tq.hyde_answer:
                with measure("retrieval.hyde_embed_ms"):
                    hyde_vec = await self.dense.embeddings.aembed([tq.hyde_answer])
                dense_results = (
                    await self.dense.retrieve_with_vector(hyde_vec[0].tolist(), tenant_id, dense_top)
                    if dense_top
                    else []
                )
                ctx.dense_candidates.extend(dense_results)
            else:
                ctx.dense_candidates.extend(
                    await self.dense.retrieve(search_query, tenant_id, dense_top) if dense_top else []
                )

            with measure("retrieval.bm25_latency_ms"):
                bm25_top = self.settings.bm25_top_k
                ctx.bm25_candidates = (
                    self.bm25.search(search_query, tenant_id, bm25_top) if bm25_top else []
                )

            if tq.expanded:
                for variant in tq.expanded:
                    expanded_dense = await self.dense.retrieve(variant, tenant_id, dense_top // 2)
                    ctx.dense_candidates.extend(expanded_dense)

            if tq.multi_queries:
                for mq in tq.multi_queries:
                    mq_dense = await self.dense.retrieve(mq, tenant_id, dense_top)
                    ctx.dense_candidates.extend(mq_dense)
                    mq_bm25 = self.bm25.search(mq, tenant_id, bm25_top) if bm25_top else []
                    ctx.bm25_candidates.extend(mq_bm25)

            rrf = RRFusioner(
                k=self.settings.rrf_k,
                dense_weight=self.settings.dense_weight,
                lexical_weight=self.settings.lexical_weight,
            )
            with measure("retrieval.rrf_fusion_ms"):
                pre_rerank = rrf.fuse(
                    ctx.dense_candidates,
                    ctx.bm25_candidates,
                    top_k=self.settings.reranker_top_k * 2,
                )
            ctx.fused_candidates = pre_rerank

            deduped = dedup_chunks(pre_rerank)

            if text_loader is not None:
                await self._hydrate(deduped, text_loader)

            with measure("retrieval.rerank_latency_ms"):
                reranked = await self.reranker.rerank(query, deduped, top_k=self.settings.reranker_top_k)
            ctx.reranked = reranked

            ctx.compressed = compress(reranked, top_k=self.settings.final_top_k)

        logger.info(
            "retrieval: dense=%d bm25=%d rerank=%d final=%d",
            len(ctx.dense_candidates),
            len(ctx.bm25_candidates),
            len(reranked),
            len(ctx.compressed),
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
