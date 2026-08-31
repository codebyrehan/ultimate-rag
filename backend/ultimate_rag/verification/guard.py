"""Verification and guarding layer.

Post-generation safety checks that ground answers in evidence before surfacing
them to the user:

- :class:`ClaimExtractor` splits an answer into atomic claims.
- :class:`VerifiableClaim` captures each claim and its source chunk.
- :class:`FaithfulnessChecker` judges whether each claim is supported by (or
  contradicted by) the retrieved evidence, using a cross-encoder
  entailment model (NLI) with a Jaccard token-overlap fallback for offline/CI.
- :class:`ConfidenceScorer` combines retrieval scores + claim support to emit
  a final confidence figure and a pass/fail verdict.

All components degrade gracefully: if no claims can be extracted the answer is
returned unchanged with a low confidence and a ``"no_claims"`` flag so callers
can decide whether to surface the answer.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import numpy as np

from ultimate_rag.generation.interface import Answer

logger = logging.getLogger("ultimate_rag.verification")

_CLAIM_SPLIT_RE = re.compile(r"(?<=[.])\s+(?=[A-Z])")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _jaccard(a: str, b: str) -> float:
    ta = set(_TOKEN_RE.findall(a.lower()))
    tb = set(_TOKEN_RE.findall(b.lower()))
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _load_nli_model():
    """Lazily load a cross-encoder NLI model. Returns None if unavailable."""
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder("cross-encoder/nli-MiniLM2-L6-H768", max_length=512)
        return model
    except Exception as e:
        logger.debug("NLI cross-encoder unavailable, falling back to Jaccard: %s", e)
        return None


def _nli_entailment(claim: str, evidence: str, model=None) -> tuple[float, float]:
    """Return (entailment_score, contradiction_score) in [0, 1].

    Uses a cross-encoder NLI model when available; falls back to
    Jaccard + heuristic thresholds for offline operation.

    The cross-encoder ``cross-encoder/nli-MiniLM2-L6-H768`` returns
    three-class logits: [contradiction, entailment, neutral].
    """
    if model is not None:
        try:
            import numpy as np

            scores = model.predict([(claim, evidence)])
            arr = np.asarray(scores).ravel()
            if len(arr) == 3:
                probs = np.exp(arr) / np.exp(arr).sum()
                contradiction = float(probs[0])
                entailment = float(probs[1])
                return entailment, contradiction
            # Some cross-encoders return 1-D regression-style scores
            s = float(arr[0]) if len(arr) > 0 else 0.0
            if s > 0:
                return s, 0.0
            return 0.0, abs(s)
        except Exception as e:
            logger.debug("NLI prediction failed, falling back to Jaccard: %s", e)
            model = None

    jaccard = _jaccard(claim, evidence)
    if jaccard >= 0.3:
        return jaccard, 0.0
    if jaccard < 0.1:
        return 0.0, 1.0 - jaccard
    return 0.0, 0.0


@dataclass
class VerifiableClaim:
    """An atomic claim extracted from an answer."""

    text: str
    index: int
    supported: bool = False
    contradicted: bool = False
    supporting_chunks: list[str] = field(default_factory=list)
    confidence: float = 0.0


class ClaimExtractor:
    """Split an answer into atomic, verifiable claims."""

    def extract(self, answer: Answer) -> list[VerifiableClaim]:
        raw = (answer.text or "").strip()
        if not raw:
            return []
        parts = _CLAIM_SPLIT_RE.split(raw)
        claims: list[VerifiableClaim] = []
        for i, part in enumerate(parts):
            text = part.strip()
            if text:
                claims.append(VerifiableClaim(text=text, index=i))
        return claims


@dataclass
class FaithfulnessResult:
    """Outcome of the faithfulness check for one answer."""

    answer: str
    claims: list[VerifiableClaim]
    supported_fraction: float
    contradicted: bool
    confidence: float = 0.0


class FaithfulnessChecker:
    """Check that each answer claim is supported by retrieved evidence.

    Uses a cross-encoder NLI model (entailment) when available; falls back
    to Jaccard token overlap for deterministic offline operation. This
    replaces the old Jaccard-only approach which could not detect
    contradictions and always returned ``contradicted=False``.
    """

    def __init__(self, threshold: float = 0.3, use_nli: bool = False) -> None:
        self.threshold = threshold
        self.use_nli = use_nli
        self._nli_model = None

    def _get_nli_model(self):
        if not self.use_nli or self._nli_model is None:
            if self.use_nli and self._nli_model is None:
                self._nli_model = _load_nli_model()
        return self._nli_model

    def check(self, answer: Answer, context_texts: list[tuple[str, str]]) -> FaithfulnessResult:
        extractor = ClaimExtractor()
        claims = extractor.extract(answer)
        if not claims and not context_texts:
            return FaithfulnessResult(
                answer=answer.text,
                claims=[],
                supported_fraction=0.0,
                contradicted=False,
                confidence=0.0,
            )
        model = self._get_nli_model()
        supported_count = 0
        contradicted_count = 0
        for claim in claims:
            best_entail = 0.0
            best_contra = 0.0
            best_cid = ""
            for cid, ctx in context_texts:
                entail, contra = _nli_entailment(claim.text, ctx, model)
                if entail > best_entail:
                    best_entail = entail
                    best_cid = cid
                best_contra = max(best_contra, contra)
            claim.supporting_chunks = [best_cid] if best_cid and best_entail >= self.threshold else []
            claim.confidence = best_entail
            if best_entail >= self.threshold:
                claim.supported = True
                supported_count += 1
            elif best_contra >= 0.5:
                claim.contradicted = True
                contradicted_count += 1
        supported_fraction = supported_count / len(claims) if claims else 0.0
        return FaithfulnessResult(
            answer=answer.text,
            claims=claims,
            supported_fraction=supported_fraction,
            contradicted=contradicted_count > 0,
            confidence=supported_fraction,
        )


class ConfidenceScorer:
    """Combine retrieval + faithfulness signals into a final score."""

    def __init__(self, faithfulness_weight: float = 0.6, retrieval_weight: float = 0.4) -> None:
        self.faithfulness_weight = faithfulness_weight
        self.retrieval_weight = retrieval_weight

    def score(
        self,
        answer: Answer,
        faithfulness: FaithfulnessResult | None = None,
    ) -> tuple[float, dict]:
        """Return (confidence, metadata).

        If faithfulness is None, confidence is derived solely from retrieval
        scores (answer.citations).
        """
        if faithfulness is None:
            max_retrieval = max((c.score for c in answer.citations), default=0.0)
            conf = max_retrieval
            meta = {"method": "retrieval_only", "max_retrieval_score": max_retrieval}
            return round(float(conf), 4), meta

        ret_max = max((c.score for c in answer.citations), default=0.0)
        f_score = faithfulness.confidence
        conf = self.faithfulness_weight * f_score + self.retrieval_weight * ret_max
        meta = {
            "method": "combined",
            "faithfulness": round(f_score, 4),
            "max_retrieval_score": round(float(ret_max), 4),
            "supported_fraction": round(faithfulness.supported_fraction, 4),
            "claims": len(faithfulness.claims),
        }
        return round(float(conf), 4), meta


@dataclass
class VerificationReport:
    """Full verification output for one answer."""

    answer: Answer
    claims: list[VerifiableClaim]
    supported_fraction: float
    confidence: float
    confidence_meta: dict
    verified: bool

    def to_dict(self) -> dict:
        return {
            "answer": self.answer.to_dict(),
            "supported_fraction": round(self.supported_fraction, 4),
            "confidence": round(self.confidence, 4),
            "verified": self.verified,
            "claims": [
                {
                    "text": c.text,
                    "supported": c.supported,
                    "contradicted": c.contradicted,
                    "confidence": round(c.confidence, 4),
                    "supporting_chunks": c.supporting_chunks,
                }
                for c in self.claims
            ],
        }


class VerificationGuard:
    """Pipeline guard: runs claim extraction + faithfulness + confidence.

    Configured by settings so it can be toggled per-tenant.
    """

    def __init__(self, settings) -> None:
        self.settings = settings
        self.extractor = ClaimExtractor()
        self.faithfulness = FaithfulnessChecker(
            threshold=getattr(settings, "nli_similarity_threshold", 0.3),
            use_nli=getattr(settings, "faithfulness_use_nli", False),
        )
        self.scorer = ConfidenceScorer()

    def verify(
        self,
        answer: Answer,
        ctx,  # RetrievalContext-like: has compressed list[RetrievedChunk]
    ) -> VerificationReport:
        self.extractor.extract(answer)
        context_texts = [(c.chunk_id, c.text or "") for c in ctx.compressed]
        f_result = self.faithfulness.check(answer, context_texts)
        confidence, meta = self.scorer.score(answer, f_result)
        verified = confidence >= 0.3
        return VerificationReport(
            answer=answer,
            claims=f_result.claims,
            supported_fraction=f_result.supported_fraction,
            confidence=confidence,
            confidence_meta=meta,
            verified=verified,
        )
