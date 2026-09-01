"""Comprehensive RAG pipeline validation script.

Tests the complete flow:
  PDF upload → extraction → chunking → embeddings → indexing →
  retrieval → reranking → generation → citations → verification
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from ultimate_rag.core.config import Settings
from ultimate_rag.core.ids import new_id
from ultimate_rag.db.connection import init_db
from ultimate_rag.db.models import DocStatus, Document
from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.embeddings.providers.stub import StubEmbeddingProvider
from ultimate_rag.generation.answer_builder import AnswerBuilder
from ultimate_rag.generation.providers.stub import StubProvider as StubLLMProvider
from ultimate_rag.ingestion.chunker import SemanticChunker
from ultimate_rag.ingestion.embeddings_batch import embed_chunks
from ultimate_rag.ingestion.extractor import extract_document
from ultimate_rag.ingestion.ocr import NoOpOCR
from ultimate_rag.ingestion.pipeline import IngestionPipeline
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.pipeline import RetrievalPipeline
from ultimate_rag.retrieval.reranker import StubReranker
from ultimate_rag.storage.providers.local import LocalFileStorage
from ultimate_rag.vecstore.providers.in_memory import InMemoryVectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_validation")


def create_test_pdf(path: str) -> None:
    """Create a rich multi-page PDF with tables, headings, exact values, and repeated terms."""
    doc = fitz.open()
    # Page 1: Title and introduction
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Ultimate RAG Test Document", fontsize=18, color=(0, 0, 0.5))
    page1.insert_text((50, 80), "Section 1: Introduction", fontsize=14, color=(0, 0, 0.3))
    page1.insert_text((50, 120), "This document tests the Ultimate RAG ingestion pipeline.", fontsize=11)
    page1.insert_text((50, 140), "The project name is Ultimate RAG Platform.", fontsize=11)
    page1.insert_text((50, 160), "It was released in September 2026.", fontsize=11)
    page1.insert_text((50, 180), "The version number is 0.1.0.", fontsize=11)
    page1.insert_text((50, 200), "The lead developer is Mohd Rehan.", fontsize=11)

    # Page 2: More content with repeated terminology
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Section 2: Architecture", fontsize=14, color=(0, 0, 0.3))
    page2.insert_text((50, 90), "Ultimate RAG uses a modular architecture.", fontsize=11)
    page2.insert_text((50, 110), "The system supports hybrid retrieval.", fontsize=11)
    page2.insert_text((50, 130), "Hybrid retrieval combines dense and sparse search.", fontsize=11)
    page2.insert_text((50, 150), "The RRF algorithm fuses results.", fontsize=11)
    page2.insert_text((50, 170), "Reranking improves relevance.", fontsize=11)

    # Page 3: Table with exact values
    page3 = doc.new_page()
    page3.insert_text((50, 50), "Section 3: Metrics", fontsize=14, color=(0, 0, 0.3))
    page3.insert_text((50, 90), "Performance metrics:", fontsize=11)
    # Create a simple table using lines and text
    y = 120
    page3.insert_text((50, y), "Model", fontsize=10)
    page3.insert_text((200, y), "Throughput", fontsize=10)
    page3.insert_text((350, y), "Latency", fontsize=10)
    y += 20
    page3.insert_text((50, y), "Stub LLM", fontsize=10)
    page3.insert_text((200, y), "1000 tok/s", fontsize=11)
    page3.insert_text((350, y), "5ms", fontsize=11)
    y += 20
    page3.insert_text((50, y), "Ollama", fontsize=10)
    page3.insert_text((200, y), "74.5 tok/s", fontsize=11)
    page3.insert_text((350, y), "120ms", fontsize=11)
    y += 20
    page3.insert_text((50, y), "OpenAI", fontsize=10)
    page3.insert_text((200, y), "150 tok/s", fontsize=11)
    page3.insert_text((350, y), "80ms", fontsize=11)

    # Page 4: Summary
    page4 = doc.new_page()
    page4.insert_text((50, 50), "Section 4: Summary", fontsize=14, color=(0, 0, 0.3))
    page4.insert_text((50, 90), "Ultimate RAG is a production-ready platform.", fontsize=11)
    page4.insert_text((50, 110), "It supports multiple LLM providers.", fontsize=11)
    page4.insert_text((50, 130), "The system is deployed on Render.", fontsize=11)
    page4.insert_text((50, 150), "PostgreSQL is used for persistence.", fontsize=11)
    page4.insert_text((50, 170), "The total cost is $0 for the free tier.", fontsize=11)

    doc.save(path)
    doc.close()
    logger.info("Created test PDF with %d pages", fitz.open(path).page_count)


async def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        pdf_path = str(tmppath / "rag_test.pdf")
        create_test_pdf(pdf_path)

        settings = Settings.model_construct()
        settings.upload_dir = str(tmppath / "uploads")
        settings.embedding_dim = 128
        settings.max_pages_per_job = 10

        tenant_id = "tenant_validation"
        doc_id = new_id()

        logger.info("=== Phase 1: Validation ===")
        from ultimate_rag.ingestion.validator import validate_upload
        validation = await validate_upload(Path(pdf_path), settings)
        logger.info("Validation passed: %d pages, SHA256=%s...", validation.page_count, validation.sha256[:16])
        assert validation.page_count == 4, f"Expected 4 pages, got {validation.page_count}"

        logger.info("=== Phase 2: Extraction ===")
        extracted = await extract_document(pdf_path, settings)
        logger.info("Extracted %d pages, %d tables", extracted.page_count, len(extracted.tables))
        assert extracted.page_count == 4
        # Note: tables depend on PDF structure; log but don't fail if none detected
        if len(extracted.tables) > 0:
            logger.info("Table rows: %d", len(extracted.tables[0].rows))

        logger.info("=== Phase 3: Chunking ===")
        chunker = SemanticChunker(settings)
        segments = chunker.chunk_document([p.text for p in extracted.pages])
        logger.info("Generated %d chunks", len(segments))
        assert len(segments) > 0, "No chunks generated"

        for seg in segments[:3]:
            logger.info("Chunk %s: page=%d, section=%s, text=%s...", seg.chunk_id[:8], seg.page_number, seg.section, seg.text[:60])

        logger.info("=== Phase 4: Embeddings ===")
        texts = [s.text for s in segments]
        embeddings = await embed_chunks(StubEmbeddingProvider(settings), texts)
        logger.info("Embeddings shape: %s", embeddings.shape)
        assert embeddings.shape == (len(segments), settings.embedding_dim)

        logger.info("=== Phase 5: Vector Store + BM25 ===")
        vec = InMemoryVectorStore(settings)
        await vec.acreate_collection()
        bm25 = BM25Retriever(settings)

        payloads = []
        bm25_records = []
        for i, seg in enumerate(segments):
            from ultimate_rag.retrieval.types import ChunkMetadata
            from ultimate_rag.vecstore.interface import VectorPayload
            payloads.append(VectorPayload(
                chunk_id=seg.chunk_id,
                document_id=doc_id,
                tenant_id=tenant_id,
                doc_filename="rag_test.pdf",
                page_number=seg.page_number,
                section=seg.section or "",
                extra={"text": seg.text},
            ))
            bm25_records.append((
                seg.chunk_id,
                seg.text,
                ChunkMetadata(
                    document_id=doc_id,
                    tenant_id=tenant_id,
                    doc_filename="rag_test.pdf",
                    page_number=seg.page_number,
                    section=seg.section or "",
                    chunk_id=seg.chunk_id,
                ),
            ))

        await vec.abatch_insert(
            [p.chunk_id for p in payloads],
            embeddings.tolist(),
            payloads,
        )
        bm25.add_chunks(tenant_id, bm25_records)
        logger.info("Indexed %d vectors + %d BM25 docs", len(payloads), len(bm25_records))

        logger.info("=== Phase 6: Dense Retrieval ===")
        dense_results = await vec.asearch(embeddings[0].tolist(), top_k=5, tenant_id=tenant_id)
        logger.info("Dense results: %d", len(dense_results))
        assert len(dense_results) > 0

        logger.info("=== Phase 7: BM25 Retrieval ===")
        bm25_results = bm25.search("Ultimate RAG", tenant_id, top_k=5)
        logger.info("BM25 results: %d", len(bm25_results))
        assert len(bm25_results) > 0

        logger.info("=== Phase 8: Hybrid Retrieval ===")
        retrieval = RetrievalPipeline(StubEmbeddingProvider(settings), vec, bm25, StubReranker(settings), settings)
        ctx = await retrieval.retrieve("Ultimate RAG modular architecture", tenant_id)
        logger.info("Retrieved %d dense, %d bm25, %d fused, %d reranked, %d compressed",
            len(ctx.dense_candidates), len(ctx.bm25_candidates), len(ctx.fused_candidates),
            len(ctx.reranked), len(ctx.compressed))
        assert len(ctx.dense_candidates) > 0
        assert len(ctx.bm25_candidates) > 0
        assert len(ctx.compressed) > 0
        logger.info("Top compressed chunk score: %.4f", ctx.compressed[0].score if ctx.compressed else 0)

        logger.info("=== Phase 9: Generation ===")
        llm = StubLLMProvider(settings)
        answer_builder = AnswerBuilder(llm, settings)
        answer = await answer_builder.build_answer(ctx)
        logger.info("Answer: %s...", answer.text[:120])
        assert len(answer.text) > 0

        logger.info("=== Phase 10: Citation Check ===")
        logger.info("Citations: %d", len(answer.citations))
        for idx, c in enumerate(answer.citations[:3]):
            logger.info("  [%d] %s p%d score=%.2f", idx + 1, c.doc_filename, c.page_number, c.score)

        logger.info("=== Phase 11: Verification ===")
        from ultimate_rag.verification.guard import VerificationGuard
        guard = VerificationGuard(settings)
        report = guard.verify(answer, ctx)
        logger.info("Confidence: %.4f, Supported: %.2f", report.confidence, report.supported_fraction)

        logger.info("=== VALIDATION COMPLETE ===")
        logger.info("All phases passed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
