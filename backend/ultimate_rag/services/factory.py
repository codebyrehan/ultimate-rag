"""Provider factory: builds concrete providers from configuration."""

from __future__ import annotations

from ultimate_rag.core.config import Settings


def build_cache_provider(settings: Settings):
    from ultimate_rag.cache.providers.in_memory import InMemoryCache
    from ultimate_rag.cache.providers.redis import RedisCache

    if not settings.cache_enabled:
        return InMemoryCache()
    if settings.redis_url:
        return RedisCache(settings.redis_url, default_ttl=settings.cache_ttl_seconds)
    return InMemoryCache()


def build_embedding_provider(settings: Settings):
    if settings.embedding_provider == "local":
        from ultimate_rag.embeddings.providers.sentence_transformers import (
            SentenceTransformersProvider,
        )

        return SentenceTransformersProvider(settings)
    if settings.embedding_provider == "openai":
        from ultimate_rag.embeddings.providers.openai_compat import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(settings)
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


def build_vector_store(settings: Settings):
    if settings.vector_store_provider == "qdrant":
        from ultimate_rag.vecstore.providers.qdrant import QdrantStore

        return QdrantStore(settings)
    if settings.vector_store_provider == "in_memory":
        from ultimate_rag.vecstore.providers.in_memory import InMemoryVectorStore

        return InMemoryVectorStore(settings)
    if settings.vector_store_provider == "pgvector":
        from ultimate_rag.vecstore.providers.pgvector import PgVectorStore

        return PgVectorStore(settings)
    raise ValueError(f"Unknown vector store provider: {settings.vector_store_provider}")


def build_llm_provider(settings: Settings):
    from ultimate_rag.generation.factory import build_llm_provider as _build

    return _build(settings)


def build_reranker(settings: Settings):
    provider = settings.reranker_provider
    if provider == "cross_encoder":
        from ultimate_rag.retrieval.reranker import CrossEncoderReranker

        return CrossEncoderReranker(settings)
    if provider == "stub":
        from ultimate_rag.retrieval.reranker import StubReranker

        return StubReranker(settings)
    raise ValueError(f"Unknown reranker provider: {provider}")


def build_ocr_provider(settings: Settings):
    if settings.ocr_enabled and settings.ocr_provider == "tesseract":
        from ultimate_rag.ingestion.ocr import TesseractOCR

        return TesseractOCR(settings)
    from ultimate_rag.ingestion.ocr import NoOpOCR

    return NoOpOCR(settings)


def build_bm25_retriever(settings: Settings):
    from ultimate_rag.retrieval.bm25 import BM25Retriever

    return BM25Retriever(settings)


def build_storage(settings: Settings):
    if settings.upload_storage_provider == "s3":
        from ultimate_rag.storage.providers.s3 import S3FileStorage

        return S3FileStorage(settings)
    from ultimate_rag.storage.providers.local import LocalFileStorage

    return LocalFileStorage(settings)
