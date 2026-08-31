"""Ingestion pipeline orchestration.

Flow:
    validate -> extract (text+tables) -> OCR fallback for scanned pages
    -> semantic chunking (parent/child) -> batch embeddings
    -> vector-store index + BM25 index -> persist Chunk rows -> update status

Idempotent: re-running on the same document replaces its vectors and chunks
atomically and updates the processing status. Tenant IDs are threaded
through every indexing call.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.core.config import Settings
from ultimate_rag.core.ids import new_id
from ultimate_rag.core.metrics import inc, measure
from ultimate_rag.db.enums import DocStatus
from ultimate_rag.db.models import Chunk, Document
from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.ingestion.chunker import SemanticChunker
from ultimate_rag.ingestion.embeddings_batch import embed_chunks
from ultimate_rag.ingestion.extractor import ExtractedDocument, extract_document
from ultimate_rag.ingestion.ocr import OCRProvider
from ultimate_rag.ingestion.validator import validate_upload
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.types import ChunkMetadata
from ultimate_rag.storage.interface import FileStorage
from ultimate_rag.vecstore.interface import VectorPayload, VectorStore

logger = logging.getLogger("ultimate_rag.ingestion.pipeline")


@dataclass
class ProcessResult:
    document_id: str
    chunks_indexed: int = 0
    pages: int = 0
    tables: int = 0
    ocr_pages: int = 0
    status: str = "pending"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _ExtractResult:
    extracted: ExtractedDocument
    validation: Any
    tmp_path: str
    ocr_pages: int


class IngestionPipeline:
    """Coordinates the ingestion of a single document."""

    def __init__(
        self,
        embeddings,
        vector_store: VectorStore,
        bm25: BM25Retriever,
        chunker: SemanticChunker,
        ocr: OCRProvider,
        storage: FileStorage,
        settings: Settings,
    ) -> None:
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.bm25 = bm25
        self.chunker = chunker
        self.ocr = ocr
        self.storage = storage
        self.settings = settings

    async def process(self, document_id: str, tenant_id: str, session: AsyncSession) -> ProcessResult:
        doc_repo = DocumentRepository(session)
        doc = await doc_repo.get(tenant_id, document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found for tenant {tenant_id}")
        if doc.status == DocStatus.INDEXED:
            logger.info("Document %s already indexed", doc.id)
            return ProcessResult(document_id=doc.id, status="indexed")
        if doc.status == DocStatus.PROCESSING:
            logger.info("Document %s already processing", doc.id)
            return ProcessResult(document_id=doc.id, status="processing")

        await doc_repo.update(
            tenant_id,
            document_id,
            status=DocStatus.PROCESSING,
            indexing_status=DocStatus.PROCESSING,
        )
        await session.commit()

        try:
            with measure("ingestion.total_latency_ms"):
                result = await self._extract(doc, tenant_id)
                segments = self._chunk(result.extracted, doc)
                await self._embed_and_index(doc, tenant_id, segments, session)
                result_final = await self._finalize(doc, tenant_id, result, segments, session)
            inc("documents_ingested")
            return result_final
        except Exception as e:
            logger.exception("Ingestion failed for document %s", document_id)
            await doc_repo.update(tenant_id, document_id, status=DocStatus.FAILED, error=str(e))
            await session.commit()
            return ProcessResult(document_id=document_id, status="failed", error=str(e))

    async def _extract(self, doc: Document, tenant_id: str) -> _ExtractResult:
        if doc.file_id is None:
            raise ValueError(f"Document {doc.id} has no file_id — cannot extract")
        data = await self.storage.read(doc.file_id)
        tmp_path = os.path.join(tempfile.gettempdir(), f"ingest_{doc.id}_{new_id()}.pdf")
        Path(tmp_path).write_bytes(data)
        try:
            validation = await validate_upload(Path(tmp_path), self.settings)
            doc.sha256 = validation.sha256
            extracted = await extract_document(tmp_path, self.settings)
            ocr_pages = await self._ocr_scanned_pages(doc, tmp_path, extracted)
            return _ExtractResult(
                extracted=extracted, validation=validation, tmp_path=tmp_path, ocr_pages=ocr_pages
            )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    async def _ocr_scanned_pages(self, doc: Document, tmp_path: str, extracted: ExtractedDocument) -> int:
        if not self.ocr.available():
            return 0
        ocr_pages = 0
        for page in extracted.pages:
            if page.is_scanned:
                ocr_text = await self.ocr.ocr_page(tmp_path, page.page_number, self.settings.ocr_lang)
                if ocr_text:
                    page.text = (page.text + "\n" + ocr_text).strip()
                    ocr_pages += 1
        return ocr_pages

    def _chunk(self, extracted: ExtractedDocument, doc: Document) -> list[Any]:
        pages = [p.text for p in extracted.pages]
        segments = self.chunker.chunk_document(pages)
        for seg in segments:
            seg.metadata = {"document_id": doc.id, "doc_filename": doc.original_filename}
        return segments

    async def _embed_and_index(
        self, doc: Document, tenant_id: str, segments: list[Any], session: AsyncSession
    ) -> None:
        if not segments:
            return
        texts = [s.text for s in segments]
        embeddings = await embed_chunks(self.embeddings, texts, self.settings.embedding_batch_size)

        payloads: list[VectorPayload] = []
        chunk_rows: list[Chunk] = []
        bm25_records: list[tuple[str, str, ChunkMetadata]] = []
        for i, seg in enumerate(segments):
            payload = VectorPayload(
                chunk_id=seg.chunk_id,
                document_id=doc.id,
                tenant_id=tenant_id,
                doc_filename=doc.original_filename,
                page_number=seg.page_number,
                section=seg.section,
                subsection=seg.subsection,
                parent_id=seg.parent_id,
                chunk_type=seg.chunk_type,
                extra=seg.metadata or {},
            )
            payloads.append(payload)
            chunk_rows.append(
                Chunk(
                    id=seg.chunk_id,
                    document_id=doc.id,
                    tenant_id=tenant_id,
                    parent_id=seg.parent_id,
                    chunk_index=i,
                    page_number=seg.page_number,
                    section=seg.section,
                    subsection=seg.subsection,
                    chunk_type=seg.chunk_type,
                    text=seg.text,
                    token_count=seg.token_count,
                    metadata_={**(seg.metadata or {}), "section": seg.section},
                )
            )
            bm25_records.append(
                (
                    seg.chunk_id,
                    seg.text,
                    ChunkMetadata(
                        document_id=doc.id,
                        tenant_id=tenant_id,
                        doc_filename=doc.original_filename,
                        page_number=seg.page_number,
                        section=seg.section,
                        subsection=seg.subsection,
                        parent_id=seg.parent_id,
                        chunk_type=seg.chunk_type,
                        chunk_id=seg.chunk_id,
                    ),
                )
            )

        deleted = await self.vector_store.adelete_document(doc.id, tenant_id)
        self.bm25.delete_document(doc.id, tenant_id)
        if deleted:
            logger.info("Removed %d old vectors for document %s before reindex", deleted, doc.id)

        await self.vector_store.abatch_insert(
            [p.chunk_id for p in payloads],
            embeddings.tolist(),
            payloads,
        )
        self.bm25.add_chunks(tenant_id, bm25_records)
        chunk_repo = ChunkRepository(session)
        await chunk_repo.delete_document(tenant_id, doc.id)
        await chunk_repo.add_many(chunk_rows)

    async def _finalize(
        self,
        doc: Document,
        tenant_id: str,
        result: _ExtractResult,
        segments: list[Any],
        session: AsyncSession,
    ) -> ProcessResult:
        doc_repo = DocumentRepository(session)
        await doc_repo.update(
            tenant_id,
            doc.id,
            status=DocStatus.INDEXED,
            indexing_status=DocStatus.INDEXED,
            page_count=result.extracted.page_count,
            indexed_at=datetime.now(UTC),
            metadata_={
                **doc.metadata_,
                "tables": len(result.extracted.tables),
                "ocr_pages": result.ocr_pages,
            },
        )
        await session.commit()
        inc("documents_indexed")
        return ProcessResult(
            document_id=doc.id,
            chunks_indexed=len(segments),
            pages=result.extracted.page_count,
            tables=len(result.extracted.tables),
            ocr_pages=result.ocr_pages,
            status="indexed",
            metadata={"sha256": doc.sha256},
        )


async def build_ingestion_pipeline(container) -> IngestionPipeline:
    """Construct an IngestionPipeline from the shared service container."""
    settings = container.settings
    from ultimate_rag.services.factory import build_storage

    return IngestionPipeline(
        embeddings=container.get("embeddings"),
        vector_store=container.get("vector_store"),
        bm25=container.get("bm25"),
        chunker=SemanticChunker(settings),
        ocr=container.get("ocr"),
        storage=build_storage(settings),
        settings=settings,
    )
