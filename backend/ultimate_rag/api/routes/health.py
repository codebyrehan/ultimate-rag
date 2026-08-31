"""Health & readiness endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    components: dict[str, Any] = {}


router = APIRouter()


@router.get("/health")
async def health() -> HealthResponse:
    from ultimate_rag.core.config import settings_dump_public
    from ultimate_rag.services.container import get_container

    components: dict[str, Any] = {}
    cfg = settings_dump_public()
    container = get_container()
    try:
        vs = container.get("vector_store")
        components["vector_store"] = vs.__class__.__name__
        components["vector_store_healthy"] = str(await vs.health_check())
    except Exception as e:  # pragma: no cover - best-effort
        components["vector_store"] = f"error: {type(e).__name__}"

    try:
        from ultimate_rag.db.connection import get_async_engine

        async with get_async_engine().connect() as conn:
            await conn.exec_driver_sql("select 1")
        components["database"] = "ok"
    except Exception:
        components["database"] = "degraded"

    return HealthResponse(
        status="ok" if components.get("database") == "ok" else "degraded",
        components={**cfg, **components},
    )


@router.get("/ready")
async def ready() -> dict:
    from ultimate_rag.core.config import settings_dump_public

    return {"ready": True, **settings_dump_public()}
