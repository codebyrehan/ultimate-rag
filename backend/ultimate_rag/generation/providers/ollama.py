"""Ollama LLM provider via the Ollama REST API (httpx)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from httpx import ConnectError as HttpxConnectError

from ultimate_rag.core.errors import ProviderError
from ultimate_rag.generation.interface import LLMProvider, LLMResponse

_DEFAULT_TIMEOUT = 60.0


class OllamaProvider(LLMProvider):
    """LLM provider backed by a local Ollama server."""

    name = "ollama"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._base_url = str(settings.ollama_base_url).rstrip("/")
        self._model = settings.llm_model
        self._timeout = float(settings.llm_timeout_seconds)

    async def generate(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        import httpx

        payload = {
            "model": self._model,
            "messages": self._to_ollama_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.settings.llm_temperature,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        url = f"{self._base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except HttpxConnectError as exc:
            raise ProviderError(
                message="Could not connect to Ollama server. Is Ollama running?",
                details={"base_url": self._base_url, "error": str(exc)},
            ) from exc
        except Exception as exc:
            raise ProviderError(message=f"Ollama request failed: {exc}") from exc
        text = data.get("message", {}).get("content", "")
        return LLMResponse(
            text=text,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            model=data.get("model", self._model),
        )

    async def stream(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        import httpx

        payload = {
            "model": self._model,
            "messages": self._to_ollama_messages(messages),
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.settings.llm_temperature,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        url = f"{self._base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        import json

                        chunk = json.loads(line)
                        if chunk.get("done"):
                            break
                        message = chunk.get("message", {})
                        content = message.get("content", "")
                        if content:
                            yield content
        except HttpxConnectError as exc:
            raise ProviderError(
                message="Could not connect to Ollama server. Is Ollama running?",
                details={"base_url": self._base_url, "error": str(exc)},
            ) from exc
        except Exception as exc:
            raise ProviderError(message=f"Ollama stream failed: {exc}") from exc

    @staticmethod
    def _to_ollama_messages(messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
        return [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]

    @staticmethod
    def _to_ollama_prompt(messages: Sequence[dict[str, str]]) -> str:
        parts: list[str] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n\n".join(parts)
