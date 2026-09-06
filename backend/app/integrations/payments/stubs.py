"""Architectural stubs for the providers that are not wired to a real API yet.

They implement the full PaymentProvider interface and are disabled by default, so
billing code never special-cases them. None of them ever fakes a successful payment.
"""

from __future__ import annotations

from app.core.errors import PaymentProviderNotConfiguredError
from app.integrations.payments.base import PaymentIntent, PaymentProvider, WebhookResult


class _DisabledProvider(PaymentProvider):
    currency = "RUB"

    @property
    def enabled(self) -> bool:
        return False

    async def create_payment(
        self, *, payload: str, amount: float, description: str, title: str, user_meta: dict
    ) -> PaymentIntent:
        raise PaymentProviderNotConfiguredError(
            f"Payment provider '{self.code}' is not configured yet"
        )

    async def handle_webhook(self, body: dict, headers: dict) -> WebhookResult:
        return WebhookResult(handled=False, reason="provider_disabled")

    async def get_payment_status(self, external_payment_id: str) -> str:
        raise PaymentProviderNotConfiguredError(
            f"Payment provider '{self.code}' is not configured yet"
        )


class YooKassaPaymentProvider(_DisabledProvider):
    code = "yookassa"
    currency = "RUB"

    @property
    def enabled(self) -> bool:
        # TODO(yookassa): implement the real adapter — POST /v3/payments with an
        # Idempotence-Key, then verify inbound notifications. Until then the provider
        # stays disabled even when the env flag and credentials are present.
        return False


class PlategaPaymentProvider(_DisabledProvider):
    code = "platega"
    currency = "RUB"

    @property
    def enabled(self) -> bool:
        # TODO(platega): implement the real adapter against the Platega merchant API.
        return False


class CryptoBotPaymentProvider(_DisabledProvider):
    code = "cryptobot"
    currency = "USDT"

    @property
    def enabled(self) -> bool:
        # TODO(cryptobot): implement the real adapter against the Crypto Pay API
        # (createInvoice + webhook signature check with the app token).
        return False
