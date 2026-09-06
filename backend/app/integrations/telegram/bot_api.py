"""Thin async Telegram Bot API client (only the calls Remarka actually needs)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import logger


class TelegramBotAPI:
    def __init__(self, token: str | None = None, *, timeout: float = 15.0) -> None:
        self._token = token if token is not None else settings.TELEGRAM_BOT_TOKEN
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._token)

    async def _call(self, method: str, payload: dict[str, Any]) -> Any:
        if not self.configured:
            raise ProviderError("Telegram bot token is not configured", code="TELEGRAM_NOT_CONFIGURED")
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("telegram_api_transport_error method=%s err=%s", method, type(exc).__name__)
            raise ProviderError("Telegram API is unreachable") from exc
        if not data.get("ok"):
            # description is safe to log: it never carries the bot token.
            logger.warning("telegram_api_error method=%s desc=%s", method, data.get("description"))
            raise ProviderError(data.get("description") or "Telegram API error")
        return data.get("result")

    async def create_invoice_link(
        self,
        *,
        title: str,
        description: str,
        payload: str,
        prices: list[dict[str, Any]],
        currency: str = "XTR",
        provider_token: str = "",
    ) -> str:
        return await self._call(
            "createInvoiceLink",
            {
                "title": title,
                "description": description,
                "payload": payload,
                "provider_token": provider_token,
                "currency": currency,
                "prices": prices,
            },
        )

    async def answer_pre_checkout_query(
        self, pre_checkout_query_id: str, ok: bool, error_message: str | None = None
    ) -> Any:
        payload: dict[str, Any] = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
        if error_message:
            payload["error_message"] = error_message
        return await self._call("answerPreCheckoutQuery", payload)

    async def send_message(self, chat_id: int | str, text: str) -> Any:
        return await self._call("sendMessage", {"chat_id": chat_id, "text": text})


def get_bot_api() -> TelegramBotAPI:
    return TelegramBotAPI()
