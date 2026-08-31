"""Redis/Valkey cache provider with graceful fallback."""

from __future__ import annotations

import json
import logging
from typing import Any

from ultimate_rag.cache import CacheProvider

logger = logging.getLogger("ultimate_rag.cache.redis")


class RedisCache(CacheProvider):
    """Redis-backed cache. Degrades gracefully when Redis is unavailable.

    All keys are namespaced with a configurable prefix. TTL defaults to
    the provided ``default_ttl`` if none is specified per-key.
    """

    def __init__(self, redis_url: str, prefix: str = "rag:cache", default_ttl: int = 300) -> None:
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._client: Any = None
        self._unavailable: bool = False

    def _get_client(self):
        if self._client is None and not self._unavailable:
            try:
                import redis

                self._client = redis.from_url(self._redis_url, decode_responses=False)
            except Exception as e:
                logger.warning("Redis unavailable, cache disabled: %s", e)
                self._unavailable = True
        return self._client

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> bytes | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            return client.get(self._key(key))
        except Exception as e:
            logger.debug("Redis get failed for %s: %s", key, e)
            return None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            client.set(self._key(key), value, ex=ttl if ttl is not None else self._default_ttl)
        except Exception as e:
            logger.debug("Redis set failed for %s: %s", key, e)

    async def delete(self, key: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            return bool(client.delete(self._key(key)))
        except Exception as e:
            logger.debug("Redis delete failed for %s: %s", key, e)
            return False

    async def exists(self, key: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            return bool(client.exists(self._key(key)))
        except Exception as e:
            logger.debug("Redis exists failed for %s: %s", key, e)
            return False

    async def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    @staticmethod
    def serialize(value: Any) -> bytes:
        """Serialize a Python object to bytes for caching."""
        return json.dumps(value, default=str).encode("utf-8")

    @staticmethod
    def deserialize(data: bytes) -> Any:
        """Deserialize bytes back to a Python object."""
        return json.loads(data.decode("utf-8"))
