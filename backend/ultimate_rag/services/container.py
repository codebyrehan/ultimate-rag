"""Service container / dependency wiring.

Holds shared, lazily-initialized services and the provider factory. Each
provider is constructed on first access from :class:`Settings`, so swapping
an embedding/LLM/vector store provider is purely configuration-driven.
Resolved providers are cached for the process lifetime (models are expensive
to load).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import cached_property
from typing import Any

from ultimate_rag.core.config import Settings, get_settings

logger = logging.getLogger("ultimate_rag.services")


class ServiceContainer:
    """In-process service locator. Providers are lazy + cached per process."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._provider_factories: dict[str, Callable[[], Any]] = {}
        self._provider_cache: dict[str, Any] = {}

    # ---- provider registration ----
    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        self._provider_factories[name] = factory
        self._provider_cache.pop(name, None)

    def get(self, name: str) -> Any:
        if name in self._provider_cache:
            return self._provider_cache[name]
        if name not in self._provider_factories:
            raise KeyError(f"No provider registered for {name!r}")
        provider = self._provider_factories[name]()
        self._provider_cache[name] = provider
        return provider

    @cached_property
    def settings_ref(self) -> Settings:
        return self.settings


_container: ServiceContainer | None = None


def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = ServiceContainer()
        _register_defaults(_container)
    return _container


def _register_defaults(container: ServiceContainer) -> None:
    """Register provider factories. Imported lazily to avoid phase-order cycles."""
    settings = container.settings
    from ultimate_rag.services import factory as F

    container.register_factory("embeddings", lambda: F.build_embedding_provider(settings))
    container.register_factory("vector_store", lambda: F.build_vector_store(settings))
    container.register_factory("llm", lambda: F.build_llm_provider(settings))
    container.register_factory("reranker", lambda: F.build_reranker(settings))
    container.register_factory("ocr", lambda: F.build_ocr_provider(settings))
    container.register_factory("bm25", lambda: F.build_bm25_retriever(settings))
    container.register_factory("cache", lambda: F.build_cache_provider(settings))


def reset_container() -> None:
    """Clear cached providers (used by tests)."""
    global _container
    _container = None
