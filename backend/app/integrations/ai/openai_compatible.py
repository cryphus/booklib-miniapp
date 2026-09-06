"""OpenAI-compatible adapters. Any vendor exposing /chat/completions and /embeddings works."""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import logger
from app.integrations.ai.base import ChatMessage, EmbeddingProvider, LLMProvider, LLMResponse


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.EMBEDDING_API_KEY
        self._base_url = (base_url or settings.EMBEDDING_BASE_URL).rstrip("/")
        self.model = model or settings.EMBEDDING_MODEL
        self.dimensions = dimensions or settings.EMBEDDING_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise ProviderError("Embedding provider is not configured", code="AI_NOT_CONFIGURED")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self.model, "input": texts},
                )
                if response.status_code >= 400:
                    logger.warning("embedding_http_status=%s", response.status_code)
                    raise ProviderError("Embedding provider returned an error")
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("embedding_transport_error err=%s", type(exc).__name__)
            raise ProviderError("Embedding provider is unreachable") from exc

        rows = sorted(payload.get("data", []), key=lambda d: d.get("index", 0))
        return [row["embedding"] for row in rows]


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(
        self, api_key: str | None = None, base_url: str | None = None, model: str | None = None
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self._base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> LLMResponse:
        if not self._api_key:
            raise ProviderError("LLM provider is not configured", code="AI_NOT_CONFIGURED")
        body: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
                if response.status_code >= 400:
                    logger.warning("llm_http_status=%s", response.status_code)
                    raise ProviderError("LLM provider returned an error")
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("llm_transport_error err=%s", type(exc).__name__)
            raise ProviderError("LLM provider is unreachable") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("LLM provider returned an unexpected payload") from exc
        return LLMResponse(content=content, raw=payload)
