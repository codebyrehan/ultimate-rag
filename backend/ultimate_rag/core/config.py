from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Server ----
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_reload: bool = True

    # ---- Database ----
    database_url: str = "sqlite+aiosqlite:///./rag.db"
    db_pool_size: int = 20
    db_max_overflow: int = 20

    # ---- Redis / queue ----
    redis_url: str = "redis://localhost:6379/0"
    inline_worker: bool = True
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300

    # ---- Security ----
    secret_key: SecretStr = Field(
        default=SecretStr("dev-only-change-me-in-production-7f3a9c1e"),
        min_length=16,
        description="Use .env to override in production",
    )

    @property
    def is_default_secret(self) -> bool:
        return self.secret_key.get_secret_value() == "dev-only-change-me-in-production-7f3a9c1e"

    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 3600
    refresh_expire_seconds: int = 86400
    bcrypt_rounds: int = 12

    # ---- Uploads ----
    upload_storage_provider: str = "local"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50
    allowed_mime_types: str = "application/pdf"

    # ---- Rate limiting ----
    rate_limit_enabled: bool = True
    rate_limit_register_per_min: int = 10
    rate_limit_login_per_min: int = 20
    rate_limit_upload_per_min: int = 10
    rate_limit_query_per_min: int = 60

    # ---- CORS ----
    cors_origins: str = "http://localhost:3000"

    # ---- Embeddings ----
    embedding_provider: str = Field(default="local", pattern="^(local|openai)$")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_batch_size: int = 32
    embedding_max_length: int = 512
    embedding_device: str = "cpu"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = ""

    # ---- Vector store ----
    vector_store_provider: str = Field(default="in_memory", pattern="^(in_memory|qdrant|pgvector)$")
    qdrant_url: str = "http://localhost:6333"
    vector_store_collection: str = "rag_chunks"
    use_ivf_index: bool = True
    hnsw_m: int = 32
    hnsw_ef: int = 128

    # ---- BM25 ----
    bm25_provider: str = "sklearn"
    bm25_top_k: int = 20

    # ---- Reranker ----
    reranker_provider: str = "cross_encoder"
    reranker_model: str = "thenlper/gte-reranker-multilingual-large"
    reranker_top_k: int = 20
    reranker_min_score: float = -10.0

    # ---- Chunking ----
    chunker_provider: str = "semantic"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    parent_chunk_size: int = 4000
    chunk_sentence_thresh: int = 110

    # ---- Ingestion ----
    ocr_provider: str = "tesseract"
    ocr_enabled: bool = True
    ocr_lang: str = "eng"
    tables_enabled: bool = True
    max_pages_per_job: int = 2000
    max_embedding_workers: int = 2

    # ---- Retrieval ----
    dense_retrieval_enabled: bool = True
    dense_top_k: int = 20
    dense_weight: float = 0.6
    lexical_weight: float = 0.4
    rrf_k: int = 60
    rrf_dedup: bool = False
    final_top_k: int = 10
    hybrid_fusion: str = "topk"

    # ---- Query transformation ----
    query_rewrite_enabled: bool = True
    query_expansion_enabled: bool = False
    query_expansion_max_variants: int = 3
    multi_query_enabled: bool = False
    hyde_enabled: bool = False
    followup_detection: bool = True

    # ---- LLM ----
    llm_provider: str = Field(default="ollama", pattern="^(ollama|openai|hf|stub)$")
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    llm_top_p: float = 0.9
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3
    llm_streaming_enabled: bool = True
    local_hf_model: str = ""
    local_hf_max_new_tokens: int = 512

    # ---- Verification ----
    claim_extraction_enabled: bool = True
    faithfulness_check_enabled: bool = True
    relevance_check_enabled: bool = True
    confidence_enabled: bool = True
    nli_similarity_threshold: float = 0.65
    faithfulness_use_nli: bool = False

    # ---- Observability ----
    log_level: str = "INFO"
    log_format: str = "json"
    metrics_enabled: bool = True
    enable_request_logging: bool = True

    # ---- Tenants ----
    default_tenant_id: str = "tenant_local"

    @field_validator("database_url")
    @classmethod
    def _db_url(cls, v: str) -> str:
        if "sqlite" in v and "aiosqlite" not in v and v.startswith("sqlite"):
            v = v.replace("sqlite:", "sqlite+aiosqlite:")
        if v.startswith("postgresql://"):
            userinfo = v.split("://")[1].split("/")[0]
            if "+" not in userinfo:
                v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def allowed_mime_list(self) -> list[str]:
        return [m.strip() for m in self.allowed_mime_types.split(",") if m.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def settings_dump_public() -> dict[str, Any]:
    """Return a safe, non-secret snapshot of settings for health checks."""
    s = get_settings()
    return {
        "database_url": "sqlite" if s.is_sqlite else "postgresql",
        "vector_store_provider": s.vector_store_provider,
        "embedding_provider": s.embedding_provider,
        "llm_provider": s.llm_provider,
        "ocr_enabled": s.ocr_enabled,
        "inline_worker": s.inline_worker,
    }
