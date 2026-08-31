"""File storage abstraction (Strategy pattern).

Stores uploaded files by a server-generated, opaque id so the user-supplied
filename never reaches the filesystem (defense against path traversal).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

from ultimate_rag.core.config import Settings


@dataclass
class StoredFile:
    file_id: str
    filename: str  # sanitized basename only
    path: str
    size: int


class FileStorage(abc.ABC):
    name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abc.abstractmethod
    async def save(self, original_name: str, data: bytes) -> StoredFile: ...

    @abc.abstractmethod
    async def read(self, file_id: str) -> bytes: ...

    @abc.abstractmethod
    async def delete(self, file_id: str) -> bool: ...

    @abc.abstractmethod
    async def exists(self, file_id: str) -> bool: ...
