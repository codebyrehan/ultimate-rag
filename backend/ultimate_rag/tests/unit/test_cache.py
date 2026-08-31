"""Tests for the cache abstraction."""

from __future__ import annotations

import asyncio

import pytest

from ultimate_rag.cache import make_cache_key
from ultimate_rag.cache.providers.in_memory import InMemoryCache
from ultimate_rag.cache.providers.redis import RedisCache


@pytest.mark.asyncio
async def test_in_memory_cache_set_get():
    cache = InMemoryCache()
    await cache.set("key1", b"value1", ttl=60)
    assert await cache.get("key1") == b"value1"


@pytest.mark.asyncio
async def test_in_memory_cache_miss():
    cache = InMemoryCache()
    assert await cache.get("nonexistent") is None


@pytest.mark.asyncio
async def test_in_memory_cache_delete():
    cache = InMemoryCache()
    await cache.set("key1", b"value1")
    assert await cache.delete("key1") is True
    assert await cache.get("key1") is None


@pytest.mark.asyncio
async def test_in_memory_cache_exists():
    cache = InMemoryCache()
    await cache.set("key1", b"value1")
    assert await cache.exists("key1") is True
    assert await cache.exists("key2") is False


@pytest.mark.asyncio
async def test_in_memory_cache_ttl_expiry():
    cache = InMemoryCache()
    await cache.set("ephemeral", b"data", ttl=1)
    assert await cache.get("ephemeral") == b"data"
    await asyncio.sleep(1.1)
    assert await cache.get("ephemeral") is None


@pytest.mark.asyncio
async def test_in_memory_cache_no_ttl_persists():
    cache = InMemoryCache()
    await cache.set("persistent", b"data")
    assert await cache.get("persistent") == b"data"
    await asyncio.sleep(0.1)
    assert await cache.get("persistent") == b"data"


def test_cache_key_tenant_isolation():
    k1 = make_cache_key("embed", "tenant_a", "text_hash", version="v1")
    k2 = make_cache_key("embed", "tenant_b", "text_hash", version="v1")
    assert k1 != k2


def test_cache_key_user_scope():
    k1 = make_cache_key("embed", "tenant_a", "text_hash", user_id="u1")
    k2 = make_cache_key("embed", "tenant_a", "text_hash", user_id="u2")
    assert k1 != k2


def test_cache_key_doc_scope():
    k1 = make_cache_key("embed", "tenant_a", "text_hash", doc_id="doc1")
    k2 = make_cache_key("embed", "tenant_a", "text_hash", doc_id="doc2")
    assert k1 != k2


def test_cache_key_version():
    k1 = make_cache_key("embed", "tenant_a", "text_hash", version="v1")
    k2 = make_cache_key("embed", "tenant_a", "text_hash", version="v2")
    assert k1 != k2


def test_cache_key_deterministic():
    k1 = make_cache_key("embed", "tenant_a", "text_hash", version="v1")
    k2 = make_cache_key("embed", "tenant_a", "text_hash", version="v1")
    assert k1 == k2


@pytest.mark.asyncio
async def test_redis_cache_unavailable_fallback():
    cache = RedisCache("redis://localhost:6379/0")
    val = await cache.get("test_key")
    assert val is None
    await cache.set("test_key", b"data", ttl=60)
    await cache.close()
