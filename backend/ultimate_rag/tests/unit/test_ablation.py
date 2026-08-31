"""Tests for the ablation study runner using stub retrievers."""

from __future__ import annotations

import json
from pathlib import Path

from ultimate_rag.evaluation.ablation import (
    _concat_strategy,
    _rrf_strategy,
)
from ultimate_rag.retrieval.types import ChunkMetadata, RetrievedChunk


def _make_chunks(ids: list[str]) -> list[RetrievedChunk]:
    meta = ChunkMetadata(
        document_id="doc1",
        tenant_id="t1",
        doc_filename="test.pdf",
        page_number=1,
    )
    return [RetrievedChunk(chunk_id=i, text=f"chunk {i}", score=1.0, metadata=meta) for i in ids]


def test_concat_strategy_dedupes():
    dense = _make_chunks(["a", "b", "c"])
    bm25 = _make_chunks(["b", "d", "e"])
    result = _concat_strategy(dense, bm25, k=4)
    assert len(result) == 4
    assert [c.chunk_id for c in result] == ["a", "b", "c", "d"]


def test_concat_strategy_respects_k():
    dense = _make_chunks(["a", "b", "c"])
    bm25 = _make_chunks(["d", "e", "f"])
    result = _concat_strategy(dense, bm25, k=2)
    assert len(result) == 2


def test_rrf_fusion():
    dense = _make_chunks(["a", "b", "c"])
    bm25 = _make_chunks(["c", "d", "e"])
    result = _rrf_strategy(dense, bm25, k=5)
    assert len(result) == 5
    ids = [c.chunk_id for c in result]
    assert "c" in ids


def test_dataset_jsonl_loads():
    from ultimate_rag.evaluation import load_dataset

    dataset_path = Path(__file__).resolve().parents[4] / "evaluation" / "datasets" / "handbook_qa.jsonl"
    examples = load_dataset(dataset_path)
    assert len(examples) == 23
    assert examples[0].question == "What is the annual leave entitlement?"
    assert "annual_leave_policy" in examples[0].expected_sources


def test_dataset_json_has_expected_sources():
    dataset_path = Path(__file__).resolve().parents[4] / "evaluation" / "datasets" / "handbook_qa.json"
    data = json.loads(dataset_path.read_text())
    assert len(data) == 23
    categories = {ex["category"] for ex in data}
    assert "factual" in categories
    assert "reasoning" in categories
    assert "semantic" in categories
    assert "multi_hop" in categories
    assert "adversarial" in categories
