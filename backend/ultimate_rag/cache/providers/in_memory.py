"""In-memory cache provider (single-process, thread-safe)."""

from __future__ import annotations

import asyncio
import time

from ultimate_rag.cache import CacheProvider


class InMemoryCache(CacheProvider):
    """Process-local cache with TTL support. Thread-safe via asyncio lock."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> bytes | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at <= time.monotonic():
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        async with self._lock:
            expires_at = time.monotonic() + ttl if ttl is not None else float("inf")
            self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._store.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            _, expires_at = entry
            if expires_at <= time.monotonic():
                del self._store[key]
                return False
            return True

    async def close(self) -> None:
        async with self._lock:
            self._store.clear()

    def _cleanup(self) -> None:
        """Remove expired entries (best-effort, not thread-safe — call under lock if needed)."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if exp <= now]
        for k in expired:
            self._store.pop(k, None)
