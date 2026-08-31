"""Ablation study runner comparing retrieval strategies.

Compares: dense-only, BM25-only, dense+BM25 (concatenation), and dense+BM25+RRF.
Generates a report showing the actual measured metrics for each configuration.

Usage:
    python -m ultimate_rag.evaluation.ablation --dataset path/dataset.jsonl
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ultimate_rag.core.config import get_settings
from ultimate_rag.evaluation import (
    EvaluationReport,
    evaluate_dataset,
)
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.dense import DenseRetriever
from ultimate_rag.retrieval.fusion import RRFusioner
from ultimate_rag.retrieval.types import RetrievedChunk

logger = logging.getLogger("ultimate_rag.evaluation.ablation")

K_VALUES = [1, 5, 10]
TOP_K = 20


@dataclass
class AblationResult:
    config_name: str
    report: EvaluationReport


async def _dense_retriever_strategy(
    dense: DenseRetriever, tenant_id: str, query: str, k: int
) -> list[RetrievedChunk]:
    return await dense.retrieve(query, tenant_id, k)


def _bm25_strategy(bm25: BM25Retriever, tenant_id: str, query: str, k: int) -> list[RetrievedChunk]:
    return bm25.search(query, tenant_id, k)


def _concat_strategy(
    dense_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
    k: int,
) -> list[RetrievedChunk]:
    """Naive top-k from dense then BM25."""
    combined = dense_results[:k] + bm25_results[:k]
    seen: set[str] = set()
    unique: list[RetrievedChunk] = []
    for chunk in combined:
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            unique.append(chunk)
    return unique[:k]


def _rrf_strategy(
    dense_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
    k: int,
) -> list[RetrievedChunk]:
    """RRF-fused dense + BM25."""
    rrf = RRFusioner(k=60, dense_weight=0.6, lexical_weight=0.4)
    return rrf.fuse(dense_results, bm25_results, top_k=k)


async def run_ablation(
    dataset_path: str,
    dense: DenseRetriever,
    bm25: BM25Retriever,
    tenant_id: str,
) -> dict[str, dict]:
    """Run the ablation study and return per-config metrics."""

    async def dense_only(query: str, k: int):
        return await dense.retrieve(query, tenant_id, k)

    async def bm25_only(query: str, k: int):
        return _bm25_strategy(bm25, tenant_id, query, k)

    async def concat(query: str, k: int):
        d = await dense.retrieve(query, tenant_id, TOP_K)
        b = _bm25_strategy(bm25, tenant_id, query, TOP_K)
        return _concat_strategy(d, b, k)

    async def rrf(query: str, k: int):
        d = await dense.retrieve(query, tenant_id, TOP_K)
        b = _bm25_strategy(bm25, tenant_id, query, TOP_K)
        return _rrf_strategy(d, b, k)

    configs = {
        "dense_only": dense_only,
        "bm25_only": bm25_only,
        "dense+bm25_concat": concat,
        "dense+bm25+rrf": rrf,
    }

    results: dict[str, dict] = {}
    for name, retriever_fn in configs.items():
        logger.info("Running ablation config: %s", name)
        report = await evaluate_dataset(retriever_fn, dataset_path)
        results[name] = report.to_dict()
        results[name]["results"] = [
            {
                "question": r.question,
                "recall_at_5": round(r.recall_at_5, 4),
                "recall_at_10": round(r.recall_at_10, 4),
                "mrr": round(r.reciprocal_rank, 4),
                "ndcg_at_5": round(r.ndcg_at_5, 4),
                "ndcg_at_10": round(r.ndcg_at_10, 4),
            }
            for r in report.results
        ]

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG ablation study runner")
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--output", default="ablation_result.json", help="Output report file")
    args = parser.parse_args()

    from ultimate_rag.services.container import get_container

    settings = get_settings()
    container = get_container()
    dense = DenseRetriever(
        container.get("embeddings"),
        container.get("vector_store"),
        settings,
    )
    bm25 = BM25Retriever(settings)

    results = asyncio.run(run_ablation(args.dataset, dense, bm25, settings.default_tenant_id))

    print(json.dumps(results, indent=2))
    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=2))
    logger.info("Ablation report saved to %s", output_path)


if __name__ == "__main__":
    main()
