"""Rate limiting middleware (in-memory sliding window).

Applies per-route-per-client limits configured in settings. The client key
combines the route prefix, the authenticated user (decoded from the Bearer
token, best-effort), and the client IP as a fallback. A 429 response with a
``Retry-After`` header is returned when the window is exhausted.

This is a process-local limiter suitable for single-instance deployments.
For multi-process scaling, swap in a Redis-backed store implementing the
``RateLimitStore`` interface.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import Request, status
from fastapi.responses import JSONResponse

WINDOW_SECONDS = 60


class _RequestLike(Protocol):
    """Structural type for request-like objects (allows test doubles)."""

    @property
    def headers(self) -> Any: ...
    @property
    def url(self) -> Any: ...
    @property
    def client(self) -> Any: ...


@dataclass
class _Bucket:
    timestamps: list[float] = field(default_factory=list)


class RateLimitStore(Protocol):
    """Minimal store interface for rate-limit counters."""

    def prune(self, key: str, now: float, window: float) -> int:
        """Drop expired timestamps and return the remaining count."""
        ...

    def record(self, key: str, now: float) -> None:
        """Record a hit for ``key`` at ``now``."""
        ...


@dataclass
class _InMemoryStore:
    """Process-local sliding-window store (thread-safe via the GIL)."""

    _buckets: dict[str, _Bucket] = field(default_factory=lambda: defaultdict(_Bucket))

    def prune(self, key: str, now: float, window: float) -> int:
        bucket = self._buckets[key]
        cutoff = now - window
        bucket.timestamps = [t for t in bucket.timestamps if t >= cutoff]
        return len(bucket.timestamps)

    def record(self, key: str, now: float) -> None:
        self._buckets[key].timestamps.append(now)


class RateLimiter:
    """Sliding-window rate limiter keyed by (route, client)."""

    def __init__(self, store: RateLimitStore | None = None) -> None:
        self.store: RateLimitStore = store or _InMemoryStore()

    def reset(self) -> None:
        """Clear all buckets (used in tests)."""
        self.store = _InMemoryStore()

    def _client_id(self, request: _RequestLike) -> str:
        # best-effort: decode the bearer token to get the user id
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            try:
                from ultimate_rag.auth.session import decode_access_token

                payload = decode_access_token(token)
                return f"u:{payload.sub}"
            except Exception:
                pass
        # fall back to client IP
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        client = request.client
        return f"ip:{client.host if client else 'unknown'}"

    def check(self, request: _RequestLike, limit: int, key_prefix: str) -> bool:
        client = self._client_id(request)
        now = time.monotonic()
        full_key = f"{key_prefix}:{client}"
        count = self.store.prune(full_key, now, WINDOW_SECONDS)
        if count >= limit:
            return False
        self.store.record(full_key, now)
        return True

    def retry_after(self, request: _RequestLike, limit: int, key_prefix: str) -> float:
        client = self._client_id(request)
        now = time.monotonic()
        full_key = f"{key_prefix}:{client}"
        bucket = self.store._buckets.get(full_key)  # type: ignore[attr-defined]
        if not bucket or not bucket.timestamps:
            return WINDOW_SECONDS
        oldest = min(bucket.timestamps)
        return max(0.0, WINDOW_SECONDS - (now - oldest))


def _route_key(path: str) -> str:
    """Map a request path to a route category for per-route limits."""
    if path.startswith("/auth/register"):
        return "register"
    if path.startswith("/auth/login"):
        return "login"
    if path.startswith("/documents/upload"):
        return "upload"
    if path.startswith("/search/query") or path.startswith("/chat"):
        return "query"
    if path.startswith("/documents") or path.startswith("/jobs"):
        return "query"
    return "default"


# Module-level singleton so the app (created once at import) and tests share
# the same limiter instance, which can be reset between tests.
_global_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter()
    return _global_limiter


def reset_rate_limits() -> None:
    """Clear the global rate-limit buckets (test utility)."""
    global _global_limiter
    if _global_limiter is not None:
        _global_limiter.reset()


def rate_limit_middleware(limiter: RateLimiter | None = None):
    """Build a Starlette HTTP middleware that enforces per-route rate limits."""

    if limiter is None:
        limiter = get_rate_limiter()

    async def _middleware(request: Request, call_next):
        from ultimate_rag.core.config import get_settings

        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)
        key = _route_key(request.url.path)
        limit_name = f"rate_limit_{key}_per_min"
        limit = getattr(settings, limit_name, settings.rate_limit_query_per_min)
        if not limiter.check(request, limit, key):
            retry = limiter.retry_after(request, limit, key)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "rate_limit_exceeded", "retry_after_seconds": round(retry, 1)},
                headers={"Retry-After": str(round(retry))},
            )
        return await call_next(request)

    return _middleware
