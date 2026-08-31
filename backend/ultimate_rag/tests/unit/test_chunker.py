from __future__ import annotations

from ultimate_rag.core.config import get_settings
from ultimate_rag.ingestion.chunker import SemanticChunker


def test_chunker_splits_into_semantic_chunks():
    s = get_settings()
    chunker = SemanticChunker(s)
    pages = [
        "This is the first paragraph about leave policy. "
        "Employees get 20 days.\n\n"
        "Second para about managers. Managers get 25 days."
    ]
    children = chunker.chunk_pages(pages)
    assert len(children) >= 1
    assert all(c.page_number == 1 for c in children)
    assert all(c.chunk_type == "child" for c in children)


def test_chunker_assigns_sections_and_parents():
    s = get_settings()
    chunker = SemanticChunker(s)
    page = (
        "Leave Policy\n"
        "Full-time employees accrue 20 days of annual leave per year.\n"
        "Managers accrue 25 days of annual leave per year.\n\n"
        "Remote Work Policy\n"
        "Remote work is permitted up to three days per week.\n"
    )
    children = chunker.chunk_pages([page])
    parents = chunker.make_parents(children)
    assert len(parents) >= 1
    sections = {c.section for c in children}
    assert "Leave Policy" in sections
    assert "Remote Work Policy" in sections
    for c in children:
        assert c.parent_id is not None


def test_token_count_positive():
    from ultimate_rag.ingestion.chunker import _token_count

    assert _token_count("hello world foo bar") > 0
