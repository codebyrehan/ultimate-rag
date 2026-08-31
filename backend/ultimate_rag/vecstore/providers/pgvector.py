"""pgvector vector store provider.

Stores dense vectors directly in PostgreSQL via the ``vector`` extension.
Uses a dedicated sync engine (psycopg3) wrapped in ``asyncio.to_thread`` so
the async interface is preserved. A single ``vector_chunks`` table holds the
embedding, the tenant id and the retrieval payload. Use this when you want
vectors co-located with metadata in PostgreSQL.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine

from ultimate_rag.core.config import Settings
from ultimate_rag.vecstore.interface import ScoredVector, VectorPayload, VectorStore

logger = logging.getLogger("ultimate_rag.vecstore.pgvector")

_meta = MetaData()


def _build_vector_table(dim: int) -> Table:
    return Table(
        "vector_chunks",
        _meta,
        Column("chunk_id", String(64), primary_key=True),
        Column("document_id", String(64), nullable=False, index=True),
        Column("tenant_id", String(64), nullable=False, index=True),
        Column("doc_filename", String(320)),
        Column("page_number", Integer, server_default="1"),
        Column("section", Text),
        Column("subsection", Text),
        Column("parent_id", String(64)),
        Column("chunk_type", String(32), server_default="child"),
        Column("extra", JSON, server_default="{}"),
        Column("embedding", Vector(dim), nullable=False),
        Index("idx_vector_chunks_tenant_embedding", "tenant_id", "embedding"),
    )


class PgVectorStore(VectorStore):
    name = "pgvector"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._engine: Engine | None = None
        self._table = _build_vector_table(settings.embedding_dim)

    def _sync_url(self) -> str:
        url = self.settings.database_url
        if url.startswith("postgresql+asyncpg"):
            return url.replace("postgresql+asyncpg", "postgresql+psycopg")
        return url

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self._sync_url(),
                pool_size=self.settings.db_pool_size,
                max_overflow=self.settings.db_max_overflow,
                pool_pre_ping=True,
                future=True,
            )
        return self._engine

    async def acreate_collection(self) -> None:
        def _create() -> None:
            with self._get_engine().begin() as conn:
                conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
                self._table.create(conn, checkfirst=True)
            logger.info("pgvector tables ready")

        await asyncio.to_thread(_create)

    async def abatch_insert(
        self, ids: list[str], vectors: list[list[float]], payloads: list[VectorPayload]
    ) -> None:
        if not ids:
            return
        eng = self._get_engine()
        rows = []
        for i, cid in enumerate(ids):
            p = payloads[i]
            rows.append(
                {
                    "chunk_id": cid,
                    "document_id": p.document_id,
                    "tenant_id": p.tenant_id,
                    "doc_filename": p.doc_filename,
                    "page_number": p.page_number,
                    "section": p.section,
                    "subsection": p.subsection,
                    "parent_id": p.parent_id,
                    "chunk_type": p.chunk_type,
                    "extra": p.extra or {},
                    "embedding": vectors[i],
                }
            )

        def _insert() -> None:
            with eng.begin() as conn:
                conn.execute(self._table.insert(), rows)

        await asyncio.to_thread(_insert)

    async def asearch(
        self,
        query_vector: list[float],
        top_k: int,
        tenant_id: str,
        filter: dict[str, Any] | None = None,
    ) -> list[ScoredVector]:
        clause = "tenant_id = :tenant"
        params: dict[str, Any] = {"tenant": tenant_id, "limit": top_k}
        if filter:
            for k, v in filter.items():
                if v is not None:
                    params[k] = v
                    clause += f" AND {k} = :{k}"
        vec_lit = f"[{','.join(str(x) for x in query_vector)}]"
        sql = text(
            f"""
            SELECT chunk_id, document_id, doc_filename, page_number, section,
                   subsection, parent_id, chunk_type, extra,
                   1 - (embedding <=> :q) AS score
            FROM vector_chunks
            WHERE {clause}
            ORDER BY embedding <=> :q
            LIMIT :limit
            """
        )
        params["q"] = vec_lit
        eng = self._get_engine()

        def _run() -> list[dict[str, Any]]:
            with eng.connect() as conn:
                result = conn.execute(sql, params).mappings().fetchall()
            return [dict(r) for r in result]

        rows = await asyncio.to_thread(_run)
        out: list[ScoredVector] = []
        for r in rows:
            out.append(
                ScoredVector(
                    chunk_id=r["chunk_id"],
                    score=float(r["score"] or 0.0),
                    payload=VectorPayload(
                        chunk_id=r["chunk_id"],
                        document_id=r["document_id"],
                        tenant_id=tenant_id,
                        doc_filename=r["doc_filename"],
                        page_number=int(r["page_number"] or 1),
                        section=r["section"],
                        subsection=r["subsection"],
                        parent_id=r["parent_id"],
                        chunk_type=r["chunk_type"] or "child",
                        extra=r["extra"] or {},
                    ),
                )
            )
        return out

    async def adelete_document(self, document_id: str, tenant_id: str) -> int:
        eng = self._get_engine()

        def _delete() -> int:
            with eng.begin() as conn:
                res = conn.execute(
                    text("DELETE FROM vector_chunks WHERE document_id = :d AND tenant_id = :t"),
                    {"d": document_id, "t": tenant_id},
                )
            return res.rowcount or 0

        return await asyncio.to_thread(_delete)

    async def adelete_tenant(self, tenant_id: str) -> int:
        eng = self._get_engine()

        def _delete() -> int:
            with eng.begin() as conn:
                res = conn.execute(
                    text("DELETE FROM vector_chunks WHERE tenant_id = :t"),
                    {"t": tenant_id},
                )
            return res.rowcount or 0

        return await asyncio.to_thread(_delete)

    async def health_check(self) -> bool:
        try:
            with self._get_engine().connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return True
        except Exception as e:
            logger.warning("pgvector healthcheck failed: %s", e)
            return False

    async def aclose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
        self._engine = None
