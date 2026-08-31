"""Tests for rate limiting middleware and store."""

from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from ultimate_rag.core.rate_limit import WINDOW_SECONDS, RateLimiter, reset_rate_limits


class _FakeRequest:
    """Minimal request stand-in for unit-testing the limiter."""

    def __init__(self, path: str = "/search/query", ip: str = "127.0.0.1"):
        self.headers: dict[str, str] = {}
        self.url = type("U", (), {"path": path})()
        self.client = type("C", (), {"host": ip})()


def test_rate_limiter_allows_under_limit():
    limiter = RateLimiter()
    for _ in range(10):
        assert limiter.check(_FakeRequest(), 10, "test") is True
    assert limiter.check(_FakeRequest(), 10, "test") is False


def test_rate_limiter_allows_after_window():
    from ultimate_rag.core.rate_limit import _InMemoryStore

    store = _InMemoryStore()
    limiter = RateLimiter(store)
    for _ in range(5):
        limiter.check(_FakeRequest(), 5, "w")
    assert limiter.check(_FakeRequest(), 5, "w") is False
    old = time.monotonic() - WINDOW_SECONDS - 1
    store._buckets["w:ip:127.0.0.1"].timestamps = [old] * 5
    assert limiter.check(_FakeRequest(), 5, "w") is True


def test_route_key_classification():
    from ultimate_rag.core.rate_limit import _route_key

    assert _route_key("/auth/register") == "register"
    assert _route_key("/auth/login") == "login"
    assert _route_key("/documents/upload") == "upload"
    assert _route_key("/search/query") == "query"
    assert _route_key("/chat/stream") == "query"
    assert _route_key("/health") == "default"


def test_rate_limiter_uses_user_id_when_authenticated():
    limiter = RateLimiter()
    req = _FakeRequest()
    req.headers["authorization"] = "Bearer not-a-real-token"
    client_id = limiter._client_id(req)
    assert client_id.startswith("ip:")


@pytest.mark.asyncio
async def test_429_on_excessive_requests(db_session) -> None:
    from ultimate_rag.core.config import get_settings
    from ultimate_rag.db.connection import get_session
    from ultimate_rag.main import app

    reset_rate_limits()
    s = get_settings()
    original = s.rate_limit_register_per_min
    s.rate_limit_register_per_min = 5

    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            codes = []
            for i in range(7):
                resp = await client.post(
                    "/auth/register",
                    json={
                        "email": f"u{i}@t.test",
                        "password": "Sup3rSecret!",
                        "tenant_name": "tenant",
                    },
                )
                codes.append(resp.status_code)
        assert 429 in codes
        assert codes[:5] == [201] * 5
    finally:
        s.rate_limit_register_per_min = original
        app.dependency_overrides.pop(get_session, None)
        reset_rate_limits()


@pytest.mark.asyncio
async def test_rate_limit_disabled(db_session, monkeypatch) -> None:
    from ultimate_rag.core.config import get_settings
    from ultimate_rag.db.connection import get_session
    from ultimate_rag.main import app

    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_session, None)
