"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from ultimate_rag.api.routes import auth, chat, conversations, docs, health, jobs, search
from ultimate_rag.api.routes import settings as settings_routes
from ultimate_rag.core.config import get_settings
from ultimate_rag.core.errors import RAGError, rag_exception_handler, unhandled_exception_handler
from ultimate_rag.core.logging import set_request_id
from ultimate_rag.core.rate_limit import get_rate_limiter, rate_limit_middleware

logger = logging.getLogger("ultimate_rag")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers on every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' http://localhost:* https://*; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from ultimate_rag.core.logging import configure_logging

        configure_logging(settings.log_level, settings.log_format)
        if settings.is_default_secret:
            logger.warning(
                "SECRET_KEY is using the default development value. "
                "Set a strong SECRET_KEY environment variable in production."
            )
        if settings.is_sqlite:
            from ultimate_rag.db.connection import init_db
            await init_db()
        # initialize vector store
        from ultimate_rag.services.container import get_container

        container = get_container()
        vs = container.get("vector_store")
        await vs.acreate_collection()
        yield
        from ultimate_rag.db.connection import dispose_engine

        await dispose_engine()

    app = FastAPI(
        title="Ultimate RAG Platform",
        description="Modular, open-source-first document intelligence + RAG platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    origins = settings.cors_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request ID + timing middleware
    @app.middleware("http")
    async def _request_id_and_timing(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid4())
        set_request_id(rid)
        request.state.request_id = rid
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed = (time.perf_counter() - t0) * 1000
            request.state.process_ms = elapsed
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time-ms"] = f"{elapsed:.2f}"
        return response

    # Exception handlers
    app.add_exception_handler(RAGError, rag_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Rate limiting (per-route sliding window)
    app.middleware("http")(rate_limit_middleware(get_rate_limiter()))

    # Routers
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(docs.router, prefix="/documents", tags=["documents"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(chat.router, prefix="/chat", tags=["chat"])
    app.include_router(search.router, prefix="/search", tags=["search"])
    app.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
    app.include_router(settings_routes.router, prefix="/settings", tags=["settings"])

    import os as _os
    from pathlib import Path
    _frontend_dist = Path(_os.path.join(_os.path.dirname(__file__), "..", "frontend-dist")).resolve()
    _frontend_index = _frontend_dist / "index.html"
    if _frontend_dist.is_dir() and _frontend_index.is_file():
        assets_dir = _frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/")
        async def _serve_frontend_index(request: Request):
            from starlette.responses import FileResponse
            return FileResponse(str(_frontend_index))

        @app.get("/{full_path:path}")
        async def _serve_frontend_spa(request: Request, full_path: str):
            from starlette.responses import FileResponse
            if full_path and not full_path.startswith("assets/"):
                file_path = _frontend_dist / full_path
                if file_path.is_file():
                    return FileResponse(str(file_path))
            return FileResponse(str(_frontend_index))

    @app.get("/metrics")
    async def metrics():
        from ultimate_rag.core.metrics import get_metrics_snapshot

        return get_metrics_snapshot()

    return app


app = create_app()
