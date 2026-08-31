from __future__ import annotations

import pytest

from ultimate_rag.core.config import get_settings
from ultimate_rag.generation.interface import Answer, Citation
from ultimate_rag.retrieval.types import ChunkMetadata, RetrievalContext, RetrievedChunk
from ultimate_rag.verification.guard import (
    ClaimExtractor,
    ConfidenceScorer,
    FaithfulnessChecker,
    FaithfulnessResult,
    VerificationGuard,
)


def _chunk(cid: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        text=text,
        score=0.9,
        metadata=ChunkMetadata(
            document_id="d1",
            tenant_id="t1",
            doc_filename="manual.pdf",
            page_number=1,
            chunk_id=cid,
        ),
    )


def test_claim_extractor_splits_sentences():
    answer = Answer(text="Employees accrue leave. Managers get extra days.", citations=[], confidence=0.9)
    claims = ClaimExtractor().extract(answer)
    assert len(claims) == 2
    assert "accrue leave" in claims[0].text
    assert "extra days" in claims[1].text


def test_claim_extractor_empty():
    assert ClaimExtractor().extract(Answer(text="", citations=[], confidence=0.0)) == []


def test_faithfulness_checker_supported_claim():
    checker = FaithfulnessChecker(threshold=0.3)
    answer = Answer(text="Employees accrue annual leave entitlement.", citations=[], confidence=0.9)
    ctx_texts = [("c1", "All employees accrue annual leave entitlement of 20 days")]
    result = checker.check(answer, ctx_texts)
    assert len(result.claims) == 1
    assert result.claims[0].supported is True
    assert result.supported_fraction == 1.0


def test_faithfulness_checker_unsupported_claim():
    checker = FaithfulnessChecker(threshold=0.8)
    answer = Answer(text="The cafeteria serves pizza.", citations=[], confidence=0.5)
    ctx_texts = [("c2", "Salary review happens yearly.")]
    result = checker.check(answer, ctx_texts)
    assert result.claims[0].supported is False
    assert result.supported_fraction == 0.0


def test_confidence_scorer_combined():
    scorer = ConfidenceScorer(faithfulness_weight=0.6, retrieval_weight=0.4)
    answer = Answer(
        text="Employees accrue leave.",
        citations=[Citation(chunk_id="c1", label="[1]", score=0.8, doc_filename="m.pdf", page_number=1)],
        confidence=0.0,
    )
    f_result = FaithfulnessResult(
        answer=answer.text, claims=[], supported_fraction=1.0, contradicted=False, confidence=1.0
    )
    conf, meta = scorer.score(answer, f_result)
    assert meta["method"] == "combined"
    assert conf == pytest.approx(0.6 * 1.0 + 0.4 * 0.8)


def test_confidence_scorer_retrieval_only():
    scorer = ConfidenceScorer()
    answer = Answer(
        text="Some answer.",
        citations=[Citation(chunk_id="c1", label="[1]", score=0.7, doc_filename="m.pdf", page_number=1)],
        confidence=0.0,
    )
    conf, meta = scorer.score(answer, faithfulness=None)
    assert meta["method"] == "retrieval_only"
    assert conf == pytest.approx(0.7)


def test_verification_guard_verify():
    s = get_settings()
    guard = VerificationGuard(s)
    answer = Answer(
        text="Annual leave entitlement is 20 days per year.",
        citations=[Citation(chunk_id="c1", label="[1]", score=0.92, doc_filename="h.pdf", page_number=2)],
        confidence=0.0,
    )
    ctx = RetrievalContext(
        tenant_id="t1",
        query="annual leave",
        compressed=[_chunk("c1", "employees accrue annual leave entitlement of 20 days per year")],
    )
    report = guard.verify(answer, ctx)
    assert report.verified is True
    assert report.confidence > 0.0
    assert len(report.claims) >= 1


def test_faithfulness_checker_detects_contradiction():
    """Claims that contradict the evidence (no shared tokens) should be flagged."""
    checker = FaithfulnessChecker(threshold=0.3)
    answer = Answer(text="The cafeteria serves pizza every Tuesday.", citations=[], confidence=0.5)
    ctx_texts = [("c1", "Employees accrue annual leave entitlement of 20 days")]
    result = checker.check(answer, ctx_texts)
    assert result.contradicted is True
    assert result.claims[0].supported is False


def test_verification_guard_abstains_on_unsupported():
    """Guard should not verify answers with no supporting evidence."""
    s = get_settings()
    guard = VerificationGuard(s)
    answer = Answer(
        text="The cafeteria serves pizza every Tuesday.",
        citations=[Citation(chunk_id="c1", label="[1]", score=0.1, doc_filename="h.pdf", page_number=2)],
        confidence=0.0,
    )
    ctx = RetrievalContext(
        tenant_id="t1",
        query="cafeteria menu",
        compressed=[_chunk("c1", "Salary review happens yearly.")],
    )
    report = guard.verify(answer, ctx)
    assert report.verified is False
    assert report.supported_fraction == 0.0
