"""HuggingFace ``transformers`` LLM provider (local CPU weights).

Lazy-imports ``transformers`` and ``torch`` so the rest of the package works
without those heavy dependencies installed. The model is loaded once and
cached on the provider instance.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from ultimate_rag.core.metrics import inc
from ultimate_rag.generation.interface import LLMProvider, LLMResponse

if TYPE_CHECKING:
    pass


class HFProvider(LLMProvider):
    """LLM provider backed by local HuggingFace ``transformers`` weights."""

    name = "hf"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._model_name = settings.local_hf_model or "gpt2"
        self._max_new_tokens = settings.local_hf_max_new_tokens
        self._model: Any = None
        self._tokenizer: Any = None

    def _load(self) -> tuple[Any, Any]:
        if self._model is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModelForCausalLM.from_pretrained(self._model_name)
        return self._tokenizer, self._model

    async def generate(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        tokenizer, model = self._load()
        prompt = self._to_prompt(messages)
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
        gen = await asyncio.to_thread(
            model.generate,
            **inputs,
            max_new_tokens=max_tokens or self._max_new_tokens,
            temperature=temperature if temperature is not None else self.settings.llm_temperature,
            do_sample=True,
        )
        text = tokenizer.decode(gen[0], skip_special_tokens=True)
        inc("llm_tokens_generated")
        return LLMResponse(text=text, model=self._model_name)

    @staticmethod
    def _to_prompt(messages: Sequence[dict[str, str]]) -> str:
        parts: list[str] = []
        for m in messages:
            parts.append(f"{m.get('role', 'user').upper()}: {m.get('content', '')}")
        return "\n".join(parts)
