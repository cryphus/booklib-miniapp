from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaymentIntent:
    """What a provider hands back so the frontend can start a checkout."""

    provider: str
    payload: str
    amount: float
    currency: str
    status: str = "pending"
    invoice_url: str | None = None
    external_payment_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookResult:
    """Normalized outcome of an inbound provider webhook."""

    handled: bool
    payload: str | None = None
    external_payment_id: str | None = None
    amount: float | None = None
    currency: str | None = None
    succeeded: bool = False
    reason: str | None = None


class PaymentProvider(ABC):
    code: str
    currency: str

    @property
    @abstractmethod
    def enabled(self) -> bool: ...

    @abstractmethod
    async def create_payment(
        self, *, payload: str, amount: float, description: str, title: str, user_meta: dict
    ) -> PaymentIntent: ...

    @abstractmethod
    async def handle_webhook(self, body: dict, headers: dict) -> WebhookResult: ...

    @abstractmethod
    async def get_payment_status(self, external_payment_id: str) -> str: ...

    async def cancel_subscription(self, provider_subscription_id: str) -> bool:
        """Default: nothing to cancel upstream (one-off payments)."""
        return True
