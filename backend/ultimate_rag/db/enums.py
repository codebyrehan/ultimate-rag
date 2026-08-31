"""Shared enums used by SQLAlchemy models."""

from __future__ import annotations

from enum import StrEnum


class DocStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ChunkType(StrEnum):
    CHILD = "child"
    PARENT = "parent"
    PAGE = "page"
