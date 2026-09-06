from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitError


class RateLimiterBackend(ABC):
    """Swap the in-memory backend for Redis later without touching call sites."""

    @abstractmethod
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Returns True when the call is allowed."""


class InMemoryRateLimiter(RateLimiterBackend):
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    def reset(self) -> None:
        self._buckets.clear()


_backend: RateLimiterBackend = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiterBackend:
    # TODO: return a RedisRateLimiter when RATE_LIMIT_BACKEND=redis in a clustered deployment.
    return _backend


def rate_limit(name: str, limit: int, window_seconds: int):
    """FastAPI dependency factory. Keys on the authenticated user when present, else client IP."""

    async def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        subject = getattr(request.state, "user_id", None)
        if subject is None:
            subject = request.client.host if request.client else "anonymous"
        allowed = await get_rate_limiter().hit(f"{name}:{subject}", limit, window_seconds)
        if not allowed:
            raise RateLimitError(f"Rate limit exceeded for {name}")

    return dependency
