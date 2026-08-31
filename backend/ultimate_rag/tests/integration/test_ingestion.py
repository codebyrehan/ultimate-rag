from __future__ import annotations

from pathlib import Path

import pytest

from ultimate_rag.core.config import Settings
from ultimate_rag.core.ids import new_id
from ultimate_rag.db.models import DocStatus, Document
from ultimate_rag.embeddings.providers.stub import StubEmbeddingProvider
from ultimate_rag.ingestion.chunker import SemanticChunker
from ultimate_rag.ingestion.ocr import NoOpOCR
from ultimate_rag.ingestion.pipeline import IngestionPipeline
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.storage.providers.local import LocalFileStorage
from ultimate_rag.tests._fixtures import make_sample_pdf
from ultimate_rag.vecstore.providers.in_memory import InMemoryVectorStore


def _test_settings(tmp_path: Path) -> Settings:
    s = Settings.model_construct()
    s.upload_dir = str(tmp_path / "uploads")
    s.embedding_dim = 128
    return s


async def test_validator_rejects_non_pdf(tmp_path: Path):
    from ultimate_rag.core.errors import ValidationError
    from ultimate_rag.ingestion.validator import validate_upload

    s = _test_settings(tmp_path)
    fake = tmp_path / "notpdf.txt"
    fake.write_bytes(b"hello not a pdf")
    with pytest.raises(ValidationError):
        await validate_upload(fake, s)


async def test_validator_accepts_pdf(tmp_path: Path):
    from ultimate_rag.ingestion.validator import validate_upload

    s = _test_settings(tmp_path)
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(make_sample_pdf())
    res = await validate_upload(pdf, s)
    assert res.page_count >= 1
    assert res.mime_type == "application/pdf"
    assert len(res.sha256) == 64


async def test_extractor_reads_text(tmp_path: Path):
    from ultimate_rag.ingestion.extractor import extract_document

    s = _test_settings(tmp_path)
    pdf = tmp_path / "handbook.pdf"
    pdf.write_bytes(make_sample_pdf(pages=2))
    doc = await extract_document(str(pdf), s)
    assert doc.page_count == 2
    combined = doc.all_text.lower()
    assert "leave policy" in combined or "handbook" in combined


async def test_ingestion_pipeline_end_to_end(tmp_path: Path, db_session):
    from ultimate_rag.db.repositories.documents import DocumentRepository

    s = _test_settings(tmp_path)
    storage = LocalFileStorage(s)
    # store the PDF
    pdf_bytes = make_sample_pdf(pages=2)
    stored = await storage.save("handbook.pdf", pdf_bytes)

    tenant_id = "tenant_ingest"
    owner_id = new_id()
    doc = Document(
        id=new_id(),
        tenant_id=tenant_id,
        owner_id=owner_id,
        filename=stored.filename,
        original_filename="handbook.pdf",
        sha256="0" * 64,
        file_id=stored.file_id,
        upload_path=stored.path,
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    d_repo = DocumentRepository(db_session)
    await d_repo.add(doc)
    await db_session.commit()

    # build pipeline with fast stub embeddings
    embeddings = StubEmbeddingProvider(s)
    vec = InMemoryVectorStore(s)
    await vec.acreate_collection()
    bm25 = BM25Retriever(s)
    chunker = SemanticChunker(s)
    pipeline = IngestionPipeline(embeddings, vec, bm25, chunker, NoOpOCR(s), storage, s)

    result = await pipeline.process(doc.id, tenant_id, db_session)

    assert result.status == "indexed"
    assert result.chunks_indexed > 0
    assert result.pages == 2

    # vectors indexed & searchable (tenant-scoped)
    dense = await vec.asearch(embeddings.embed(["leave policy"])[0].tolist(), top_k=5, tenant_id=tenant_id)
    assert len(dense) > 0
    # bm25 indexed
    kw = bm25.search("leave policy", tenant_id, top_k=5)
    assert len(kw) > 0
    # db chunks persisted
    from ultimate_rag.db.repositories.chunks import ChunkRepository

    chunks = await ChunkRepository(db_session).list_for_document(tenant_id, doc.id)
    assert len(chunks) >= len(dense)
    # document status updated
    updated = await d_repo.get(tenant_id, doc.id)
    assert updated is not None and updated.status == DocStatus.INDEXED
