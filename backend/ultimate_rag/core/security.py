from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from pathlib import Path

ALLOWED_NAME_CHARS = set(string.ascii_letters + string.digits + "._-")


def sanitize_filename(name: str, max_len: int = 180) -> str:
    """Return a filesystem-safe basename, stripping path components."""
    name = Path(name).name  # drops any directory traversal
    cleaned = "".join(c if c in ALLOWED_NAME_CHARS else "_" for c in name).strip("._")
    if not cleaned:
        cleaned = "file"
    return cleaned[:max_len]


def generate_api_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
