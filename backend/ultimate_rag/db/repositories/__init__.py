"""Tenant-scoped repository factories."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.db.repositories.conversations import ConversationRepository, MessageRepository
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.db.repositories.evidence import EvidenceRepository
from ultimate_rag.db.repositories.jobs import JobRepository
from ultimate_rag.db.repositories.tenants import TenantRepository
from ultimate_rag.db.repositories.users import UserRepository


def repos(session: AsyncSession) -> dict[str, object]:
    """Return all repositories bound to a session. Convenience helper."""
    return {
        "tenants": TenantRepository(session),
        "users": UserRepository(session),
        "documents": DocumentRepository(session),
        "chunks": ChunkRepository(session),
        "conversations": ConversationRepository(session),
        "messages": MessageRepository(session),
        "jobs": JobRepository(session),
        "evidence": EvidenceRepository(session),
    }
