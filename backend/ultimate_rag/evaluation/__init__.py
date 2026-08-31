"""Evaluation framework for RAG retrieval quality.

Provides standard IR retrieval metrics (Recall@K, Precision@K, MRR, nDCG) and
a runner that evaluates a retrieval pipeline against a JSONL dataset.

Dataset format (one JSON object per line):
    {
      "question": "...",
      "expected_sources": ["chunk_id_1", "chunk_id_2"],
      "document_ids": ["doc_id_1"]
    }

Usage:
    python -m ultimate_rag.evaluation.runner --dataset path/dataset.jsonl
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("ultimate_rag.evaluation")

__all__ = [
    "EvaluationExample",
    "EvaluationReport",
    "EvaluationResult",
    "evaluate_dataset",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]


@dataclass
class EvaluationExample:
    """A single evaluation instance."""

    question: str
    expected_sources: list[str]
    document_ids: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Metric values for a single example."""

    question: str
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    reciprocal_rank: float
    ndcg_at_5: float
    ndcg_at_10: float
    retrieved_ids: list[str]
    expected_ids: list[str]


@dataclass
class EvaluationReport:
    """Aggregated evaluation report across all examples."""

    results: list[EvaluationResult]
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    mean_reciprocal_rank: float
    ndcg_at_5: float
    ndcg_at_10: float
    precision_at_5: float
    total_examples: int

    def to_dict(self) -> dict:
        return {
            "total_examples": self.total_examples,
            "recall_at_1": round(self.recall_at_1, 4),
            "recall_at_5": round(self.recall_at_5, 4),
            "recall_at_10": round(self.recall_at_10, 4),
            "mean_reciprocal_rank": round(self.mean_reciprocal_rank, 4),
            "ndcg_at_5": round(self.ndcg_at_5, 4),
            "ndcg_at_10": round(self.ndcg_at_10, 4),
            "mean_precision_at_5": round(self.precision_at_5, 4),
        }


def _relevant_ranks(retrieved_ids: list[str], expected_ids: set[str]) -> list[int]:
    """Return 1-based ranks of relevant items in the retrieved list."""
    return [i + 1 for i, rid in enumerate(retrieved_ids) if rid in expected_ids]


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Fraction of relevant items found in the top-k results."""
    if not expected_ids:
        return 0.0
    hits = len(set(retrieved_ids[:k]) & set(expected_ids))
    return hits / len(expected_ids)


def precision_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Fraction of top-k results that are relevant."""
    if k == 0 or not retrieved_ids[:k]:
        return 0.0
    hits = len(set(retrieved_ids[:k]) & set(expected_ids))
    return hits / min(k, len(retrieved_ids))


def mean_reciprocal_rank(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """MRR: reciprocal of the rank of the first relevant item."""
    expected_set = set(expected_ids)
    for i, rid in enumerate(retrieved_ids):
        if rid in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """nDCG@K with binary relevance."""
    expected_set = set(expected_ids)
    dcg = 0.0
    for i, rid in enumerate(retrieved_ids[:k]):
        if rid in expected_set:
            dcg += 1.0 / (_log2(i + 2))
    ideal = min(len(expected_set), k)
    idcg = sum(1.0 / _log2(i + 2) for i in range(ideal))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def _log2(x: float) -> float:
    import math

    return math.log2(x)


def load_dataset(path: str | Path) -> list[EvaluationExample]:
    """Load examples from a JSONL file."""
    p = Path(path)
    examples: list[EvaluationExample] = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            obj = json.loads(line)
            examples.append(
                EvaluationExample(
                    question=obj["question"],
                    expected_sources=obj.get("expected_sources", []),
                    document_ids=obj.get("document_ids", []),
                )
            )
    return examples


async def evaluate_dataset(
    retriever_fn,
    dataset_path: str | Path,
    k_values: list[int] | None = None,
) -> EvaluationReport:
    """Evaluate a retrieval function against a dataset.

    Args:
        retriever_fn: async callable(query, k) -> list[retrieved_item],
            where each item has a ``chunk_id`` attribute or key.
        dataset_path: path to a JSONL dataset file.
        k_values: list of k values to compute (default [1, 5, 10]).
    """
    if k_values is None:
        k_values = [1, 5, 10]

    examples = load_dataset(dataset_path)
    results: list[EvaluationResult] = []

    for ex in examples:
        retrieved = await retriever_fn(ex.question, max(k_values))
        retrieved_ids = []
        for item in retrieved:
            if isinstance(item, str):
                retrieved_ids.append(item)
            elif hasattr(item, "chunk_id"):
                retrieved_ids.append(item.chunk_id)
            elif isinstance(item, dict):
                retrieved_ids.append(item.get("chunk_id", ""))

        expected_set = set(ex.expected_sources)
        result = EvaluationResult(
            question=ex.question,
            recall_at_1=recall_at_k(retrieved_ids, list(expected_set), 1),
            recall_at_5=recall_at_k(retrieved_ids, list(expected_set), 5),
            recall_at_10=recall_at_k(retrieved_ids, list(expected_set), 10),
            precision_at_5=precision_at_k(retrieved_ids, list(expected_set), 5),
            reciprocal_rank=mean_reciprocal_rank(retrieved_ids, ex.expected_sources),
            ndcg_at_5=ndcg_at_k(retrieved_ids, list(expected_set), 5),
            ndcg_at_10=ndcg_at_k(retrieved_ids, list(expected_set), 10),
            retrieved_ids=retrieved_ids,
            expected_ids=list(expected_set),
        )
        results.append(result)

    n = len(results)
    report = EvaluationReport(
        results=results,
        recall_at_1=sum(r.recall_at_1 for r in results) / n if n else 0.0,
        recall_at_5=sum(r.recall_at_5 for r in results) / n if n else 0.0,
        recall_at_10=sum(r.recall_at_10 for r in results) / n if n else 0.0,
        mean_reciprocal_rank=sum(r.reciprocal_rank for r in results) / n if n else 0.0,
        ndcg_at_5=sum(r.ndcg_at_5 for r in results) / n if n else 0.0,
        ndcg_at_10=sum(r.ndcg_at_10 for r in results) / n if n else 0.0,
        precision_at_5=sum(r.precision_at_5 for r in results) / n if n else 0.0,
        total_examples=n,
    )
    return report
