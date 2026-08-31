"""Tests for security headers middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_security_headers_present():
    from ultimate_rag.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in resp.headers
    assert "Permissions-Policy" in resp.headers


def test_csp_header_content():
    from ultimate_rag.main import app

    client = TestClient(app)
    resp = client.get("/health")
    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'self'" in csp
