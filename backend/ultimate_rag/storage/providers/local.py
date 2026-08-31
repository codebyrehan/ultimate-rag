"""Local filesystem file storage.

Files are stored under the configured upload dir using a server-generated
ULID-style id; the on-disk name is sanitized and never user-controlled,
neutralizing path-traversal and malicious-filename attacks.
"""

from __future__ import annotations

from pathlib import Path

from ultimate_rag.core.ids import new_id
from ultimate_rag.core.security import sanitize_filename
from ultimate_rag.storage.interface import FileStorage, StoredFile


class LocalFileStorage(FileStorage):
    name = "local"

    def __init__(self, settings):
        super().__init__(settings)
        self._root = Path(settings.upload_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, file_id: str) -> Path:
        safe = sanitize_filename(file_id, max_len=120)
        return (self._root / safe).resolve()

    async def save(self, original_name: str, data: bytes) -> StoredFile:
        file_id = new_id()
        path = self._path_for(file_id)
        # ensure the resolved path stays within the root (no traversal)
        try:
            path.relative_to(self._root.resolve())
        except ValueError as exc:
            raise ValueError("Resolved storage path escapes upload root") from exc
        with path.open("wb") as f:
            f.write(data)
        return StoredFile(
            file_id=file_id,
            filename=sanitize_filename(original_name),
            path=str(path),
            size=len(data),
        )

    async def read(self, file_id: str) -> bytes:
        path = self._path_for(file_id)
        if not path.exists():
            raise FileNotFoundError(f"Stored file {file_id} not found")
        return path.read_bytes()

    async def delete(self, file_id: str) -> bool:
        path = self._path_for(file_id)
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False

    async def exists(self, file_id: str) -> bool:
        return self._path_for(file_id).exists()
