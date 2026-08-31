"""Tests for failure scenarios and graceful degradation."""

from __future__ import annotations

import asyncio

import pytest

from ultimate_rag.cache.providers.in_memory import InMemoryCache


@pytest.mark.asyncio
async def test_cache_get_returns_none_on_keyerror():
    cache = InMemoryCache()
    assert await cache.get("missing_key") is None


@pytest.mark.asyncio
async def test_cache_set_overwrites():
    cache = InMemoryCache()
    await cache.set("key", b"v1")
    await cache.set("key", b"v2")
    assert await cache.get("key") == b"v2"


@pytest.mark.asyncio
async def test_cache_delete_returns_false_if_missing():
    cache = InMemoryCache()
    await cache.set("key", b"val")
    assert await cache.delete("key") is True
    assert await cache.delete("key") is False


@pytest.mark.asyncio
async def test_in_memory_cache_ttl_zero():
    cache = InMemoryCache()
    await cache.set("ephemeral", b"data", ttl=0)
    assert await cache.get("ephemeral") is None


@pytest.mark.asyncio
async def test_cache_concurrent_set_get():
    cache = InMemoryCache()
    await cache.set("shared", b"data")
    results = await asyncio.gather(
        cache.get("shared"),
        cache.get("shared"),
        cache.set("shared", b"updated"),
        cache.get("shared"),
    )
    assert results[0] == b"data"
    assert results[3] == b"updated"


@pytest.mark.asyncio
async def test_redis_cache_unavailable_returns_none():
    from ultimate_rag.cache.providers.redis import RedisCache

    cache = RedisCache("redis://localhost:99999/0")
    assert await cache.get("test") is None
    await cache.close()
