"""Telegram Stars (XTR) — the one payment provider that is fully live in this MVP."""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import logger
from app.integrations.payments.base import PaymentIntent, PaymentProvider, WebhookResult
from app.integrations.telegram.bot_api import TelegramBotAPI


class TelegramStarsPaymentProvider(PaymentProvider):
    code = "telegram_stars"
    currency = "XTR"

    def __init__(self, bot_api: TelegramBotAPI | None = None) -> None:
        self._bot = bot_api or TelegramBotAPI()

    @property
    def enabled(self) -> bool:
        return settings.ENABLE_TELEGRAM_STARS and self._bot.configured

    async def create_payment(
        self, *, payload: str, amount: float, description: str, title: str, user_meta: dict
    ) -> PaymentIntent:
        stars = int(amount)
        invoice_url = await self._bot.create_invoice_link(
            title=title,
            description=description,
            payload=payload,
            currency=self.currency,
            prices=[{"label": title, "amount": stars}],
            provider_token="",  # Stars invoices carry an empty provider token by design.
        )
        return PaymentIntent(
            provider=self.code,
            payload=payload,
            amount=stars,
            currency=self.currency,
            invoice_url=invoice_url,
        )

    async def handle_webhook(self, body: dict, headers: dict) -> WebhookResult:
        """Parses a Telegram update. pre_checkout_query is answered by the billing service,
        which is the only place that knows whether the payload/amount are still valid."""
        message = body.get("message") or {}
        successful = message.get("successful_payment")
        if successful:
            return WebhookResult(
                handled=True,
                payload=successful.get("invoice_payload"),
                external_payment_id=successful.get("telegram_payment_charge_id"),
                amount=float(successful.get("total_amount") or 0),
                currency=successful.get("currency"),
                succeeded=True,
            )

        pre_checkout = body.get("pre_checkout_query")
        if pre_checkout:
            return WebhookResult(
                handled=True,
                payload=pre_checkout.get("invoice_payload"),
                external_payment_id=pre_checkout.get("id"),
                amount=float(pre_checkout.get("total_amount") or 0),
                currency=pre_checkout.get("currency"),
                succeeded=False,
                reason="pre_checkout_query",
            )

        logger.info("telegram_webhook_ignored keys=%s", sorted(body.keys()))
        return WebhookResult(handled=False, reason="unsupported_update")

    async def get_payment_status(self, external_payment_id: str) -> str:
        # Telegram pushes the final state; there is no polling endpoint for Stars charges.
        return "unknown"

    async def answer_pre_checkout(self, query_id: str, ok: bool, error: str | None = None) -> None:
        await self._bot.answer_pre_checkout_query(query_id, ok, error)
