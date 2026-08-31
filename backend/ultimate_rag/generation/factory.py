"""Factory for the RAG generation layer."""

from __future__ import annotations

from ultimate_rag.core.config import Settings
from ultimate_rag.generation.answer_builder import AnswerBuilder
from ultimate_rag.generation.interface import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider
    if provider == "ollama":
        from ultimate_rag.generation.providers.ollama import OllamaProvider

        return OllamaProvider(settings)
    if provider == "openai":
        from ultimate_rag.generation.providers.openai_compat import OpenAIProvider

        return OpenAIProvider(settings)
    if provider == "hf":
        from ultimate_rag.generation.providers.hf_transformers import HFProvider

        return HFProvider(settings)
    if provider == "stub":
        from ultimate_rag.generation.providers.stub import StubProvider

        return StubProvider(settings)
    raise ValueError(f"Unknown llm provider: {provider}")


def build_answer_builder(settings: Settings, llm: LLMProvider) -> AnswerBuilder:
    """Construct an :class:`AnswerBuilder` wired to an LLM provider."""
    return AnswerBuilder(llm=llm, settings=settings)
