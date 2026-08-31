"""OpenAI-compatible LLM provider via the Chat Completions API (httpx).

Works against OpenAI, or any OpenAI-compatible endpoint (e.g. a local
http-server with the same schema), including LiteLLM proxies.
"""

from __future__ import annotations

from collections.abc import Sequence

from ultimate_rag.generation.interface import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """LLM provider backed by an OpenAI-compatible REST API."""

    name = "openai"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._api_key = settings.openai_api_key.get_secret_value() or ""
        self._base_url = str(settings.openai_base_url).rstrip("/") or "https://api.openai.com/v1"
        self._model = settings.llm_model
        self._timeout = float(settings.llm_timeout_seconds)

    async def generate(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        import httpx

        headers = {"Authorization": f"Bearer {self._api_key}"}
        body: dict = {
            "model": self._model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": temperature if temperature is not None else self.settings.llm_temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        url = f"{self._base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]
        text = choice.get("message", {}).get("content", "")
        return LLMResponse(
            text=text,
            prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
            model=data.get("model", self._model),
        )

    async def stream(self, messages, temperature=None, max_tokens=None):
        import json as _json

        import httpx

        headers = {"Authorization": f"Bearer {self._api_key}"}
        body: dict = {
            "model": self._model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": temperature if temperature is not None else self.settings.llm_temperature,
            "stream": True,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        url = f"{self._base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
