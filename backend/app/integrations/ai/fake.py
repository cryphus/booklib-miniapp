"""Deterministic offline providers. Used by the test suite and by AI_PROVIDER=fake."""

from __future__ import annotations

import hashlib
import json
import math
import re

from app.integrations.ai.base import ChatMessage, EmbeddingProvider, LLMProvider, LLMResponse

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class FakeEmbeddingProvider(EmbeddingProvider):
    """Hashed bag-of-words vector: same text always yields the same vector, and
    texts sharing words end up close together, which is enough to test retrieval."""

    def __init__(self, dimensions: int = 64, model: str = "fake-embedding") -> None:
        self.dimensions = dimensions
        self.model = model
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class FakeLLMProvider(LLMProvider):
    """Echoes back a valid Remarka answer envelope built from the supplied context."""

    def __init__(self, model: str = "fake-llm", answer: str | None = None) -> None:
        self.model = model
        self.calls: list[list[ChatMessage]] = []
        self._answer = answer

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> LLMResponse:
        self.calls.append(messages)
        user_text = "\n".join(m.content for m in messages if m.role == "user")
        source_ids = re.findall(r"\[source:([0-9a-fA-F-]{36})\]", user_text)
        answer = self._answer or (
            f"На основании {len(source_ids)} записей из вашей библиотеки."
            if source_ids
            else "В библиотеке не найдено достаточно информации."
        )
        return LLMResponse(
            content=json.dumps({"answer": answer, "source_ids": source_ids}, ensure_ascii=False)
        )
