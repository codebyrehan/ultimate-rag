from __future__ import annotations

from ultimate_rag.core.config import Settings
from ultimate_rag.retrieval.query_transform.transformer import (
    HydeGenerator,
    MultiQueryExpander,
    QueryExpander,
    QueryRewriter,
    QueryTransformConfig,
    QueryTransformer,
    StubExpander,
    build_query_transformer,
)


def test_rewriter_strips_prefixes():
    rewriter = QueryRewriter()
    assert rewriter.rewrite("Can you tell me about leave policy") == "tell me about leave policy"
    assert rewriter.rewrite("how does remote work policy apply") == "how does remote work policy apply"


def test_rewriter_normalises_case():
    rewriter = QueryRewriter()
    assert rewriter.rewrite("Leave POLICY") == "leave policy"


def test_expander_generates_synonym_variants():
    expander = QueryExpander(max_variants=3)
    variants = expander.expand("annual leave policy")
    assert any("vacation" in v for v in variants)
    assert any("rule" in v for v in variants)
    assert len(variants) <= 3


def test_expander_unknown_token_returns_empty():
    expander = QueryExpander()
    assert expander.expand("xyzzy qwerty") == []


def test_stub_expander_returns_empty():
    assert StubExpander().expand("anything at all") == []


def test_transformer_disabled_returns_original():
    cfg = QueryTransformConfig(
        rewrite_enabled=False, expansion_enabled=False, hyde_enabled=False, multi_query=False
    )
    t = QueryTransformer(cfg)
    out = t.transform("Can you explain remote policy?")
    assert out.original == "Can you explain remote policy?"
    assert out.rewritten == "Can you explain remote policy?"
    assert out.expanded == []


def test_transformer_rewrite_and_expand():
    cfg = QueryTransformConfig(
        rewrite_enabled=True,
        expansion_enabled=True,
        hyde_enabled=False,
        multi_query=False,
        max_variants=2,
    )
    t = QueryTransformer(cfg)
    out = t.transform("What is the leave policy?")
    assert out.rewritten == "what is the leave policy"
    assert len(out.expanded) > 0
    assert all(v != out.rewritten for v in out.expanded)


def test_build_query_transformer_from_settings():
    s = Settings.model_construct()
    t = build_query_transformer(s)
    assert isinstance(t.rewriter, QueryRewriter)
    assert s.query_expansion_enabled is False
    assert isinstance(t.expander, StubExpander)
    out = t.transform("some query about salary")
    assert out.expanded == []


def test_multi_query_expander_generates_variants():
    expander = MultiQueryExpander(max_variants=3)
    variants = expander.expand("leave policy")
    assert len(variants) > 0
    assert all(v != "leave policy" for v in variants)


def test_multi_query_expander_respects_max_variants():
    expander = MultiQueryExpander(max_variants=2)
    variants = expander.expand("remote work policy")
    assert len(variants) <= 2


def test_hyde_generator_produces_answer():
    gen = HydeGenerator()
    answer = gen.generate("What is the leave policy?", "what is the leave policy")
    assert isinstance(answer, str)
    assert len(answer) > 0
    assert answer.endswith(".")


def test_transformer_hyde_and_multi_query():
    cfg = QueryTransformConfig(
        rewrite_enabled=True,
        expansion_enabled=False,
        hyde_enabled=True,
        multi_query=True,
        max_variants=3,
    )
    t = QueryTransformer(cfg)
    out = t.transform("What is the leave policy?")
    assert out.hyde_answer is not None
    assert len(out.hyde_answer) > 0
    assert len(out.multi_queries) > 0


def test_transformer_disabled_hyde_and_multi_query():
    cfg = QueryTransformConfig(
        rewrite_enabled=False,
        expansion_enabled=False,
        hyde_enabled=False,
        multi_query=False,
    )
    t = QueryTransformer(cfg)
    out = t.transform("Can you explain remote policy?")
    assert out.hyde_answer is None
    assert out.multi_queries == []
