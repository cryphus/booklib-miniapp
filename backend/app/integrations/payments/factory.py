from __future__ import annotations

from app.core.errors import NotFoundError
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.stubs import (
    CryptoBotPaymentProvider,
    PlategaPaymentProvider,
    YooKassaPaymentProvider,
)
from app.integrations.payments.telegram_stars import TelegramStarsPaymentProvider

_REGISTRY: dict[str, type[PaymentProvider]] = {
    TelegramStarsPaymentProvider.code: TelegramStarsPaymentProvider,
    YooKassaPaymentProvider.code: YooKassaPaymentProvider,
    PlategaPaymentProvider.code: PlategaPaymentProvider,
    CryptoBotPaymentProvider.code: CryptoBotPaymentProvider,
}

_overrides: dict[str, PaymentProvider] = {}


class PaymentProviderFactory:
    """The billing service asks for a code and gets an interface; it knows no vendor details."""

    @staticmethod
    def get(code: str) -> PaymentProvider:
        if code in _overrides:
            return _overrides[code]
        provider_cls = _REGISTRY.get(code)
        if provider_cls is None:
            raise NotFoundError(f"Unknown payment provider '{code}'", code="UNKNOWN_PROVIDER")
        return provider_cls()

    @staticmethod
    def all() -> list[PaymentProvider]:
        return [PaymentProviderFactory.get(code) for code in _REGISTRY]

    @staticmethod
    def override(code: str, provider: PaymentProvider) -> None:
        _overrides[code] = provider

    @staticmethod
    def reset_overrides() -> None:
        _overrides.clear()
