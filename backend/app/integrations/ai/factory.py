from __future__ import annotations

from app.core.config import settings
from app.integrations.ai.base import EmbeddingProvider, LLMProvider
from app.integrations.ai.fake import FakeEmbeddingProvider, FakeLLMProvider
from app.integrations.ai.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleLLMProvider,
)

_embedding_provider: EmbeddingProvider | None = None
_llm_provider: LLMProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = (
            FakeEmbeddingProvider()
            if settings.AI_PROVIDER == "fake"
            else OpenAICompatibleEmbeddingProvider()
        )
    return _embedding_provider


def get_llm_provider() -> LLMProvider:
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = (
            FakeLLMProvider() if settings.AI_PROVIDER == "fake" else OpenAICompatibleLLMProvider()
        )
    return _llm_provider


def set_providers(
    embedding: EmbeddingProvider | None = None, llm: LLMProvider | None = None
) -> None:
    """Used by tests and by the seed script to inject offline providers."""
    global _embedding_provider, _llm_provider
    if embedding is not None:
        _embedding_provider = embedding
    if llm is not None:
        _llm_provider = llm


def reset_providers() -> None:
    global _embedding_provider, _llm_provider
    _embedding_provider = None
    _llm_provider = None
