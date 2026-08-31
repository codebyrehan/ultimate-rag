"""Integration tests for /auth/register and /auth/login."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ultimate_rag.db.connection import get_session
from ultimate_rag.main import app


@pytest.fixture
async def client(db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_register_returns_token(client) -> None:
    resp = await client.post(
        "/auth/register",
        json={
            "email": "alice@acme.test",
            "password": "Sup3rSecret!",
            "full_name": "Alice",
            "tenant_name": "acme",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client) -> None:
    payload = {
        "email": "bob@acme.test",
        "password": "Sup3rSecret!",
        "tenant_name": "acme",
    }
    await client.post("/auth/register", json=payload)
    resp2 = await client.post("/auth/register", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client) -> None:
    await client.post(
        "/auth/register",
        json={
            "email": "carol@acme.test",
            "password": "Sup3rSecret!",
            "tenant_name": "acme",
        },
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "carol@acme.test", "password": "Sup3rSecret!", "tenant_name": "acme"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token


@pytest.mark.asyncio
async def test_login_wrong_password(client) -> None:
    await client.post(
        "/auth/register",
        json={"email": "dave@acme.test", "password": "correctpw1", "tenant_name": "acme"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "dave@acme.test", "password": "wrongpw1", "tenant_name": "acme"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_weak_password_rejected(client) -> None:
    resp = await client.post(
        "/auth/register",
        json={"email": "eve@acme.test", "password": "short", "tenant_name": "acme"},
    )
    assert resp.status_code == 422
