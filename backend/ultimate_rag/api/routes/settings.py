"""Settings routes.

Exposes a simple settings read/write endpoint. Since settings are primarily
configured via environment variables, the POST endpoint currently echoes back
the provided payload. Runtime persistence can be added later if needed.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SettingsUpdateRequest(BaseModel):
    llm_provider: str | None = None
    embedding_provider: str | None = None
    vector_store_provider: str | None = None
    reranker_provider: str | None = None
    inline_worker: bool | None = None
    cache_enabled: bool | None = None
    claim_extraction_enabled: bool | None = None
    faithfulness_check_enabled: bool | None = None
    ocr_enabled: bool | None = None
    max_upload_size_mb: int | None = None


@router.get("/")
async def get_settings() -> dict:
    from ultimate_rag.core.config import settings_dump_public

    return settings_dump_public()


@router.post("/")
async def update_settings(payload: SettingsUpdateRequest) -> dict:
    from ultimate_rag.core.config import settings_dump_public

    current = settings_dump_public()
    updated = {**current}
    for key, value in payload.model_dump(exclude_none=True).items():
        updated[key] = value
    return {"status": "ok", "settings": updated}
