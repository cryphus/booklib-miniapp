from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request, Response

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.errors import APIError, UnauthorizedError
from app.core.logging import logger
from app.core.rate_limit import rate_limit
from app.integrations.payments import PaymentProviderFactory
from app.integrations.payments.telegram_stars import TelegramStarsPaymentProvider
from app.schemas.billing import (
    BillingStatusOut,
    CreateInvoiceRequest,
    InvoiceOut,
    PaymentStatusOut,
    ProviderOut,
)
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status", response_model=BillingStatusOut)
async def billing_status(user: CurrentUser, session: SessionDep) -> BillingStatusOut:
    return await BillingService(session).status(user.id)


@router.get("/providers", response_model=list[ProviderOut])
async def billing_providers() -> list[ProviderOut]:
    """The backend decides which payment methods the UI may offer."""
    return BillingService.providers()


@router.post(
    "/telegram-stars/create",
    response_model=InvoiceOut,
    dependencies=[Depends(rate_limit("billing_create", limit=10, window_seconds=300))],
)
async def create_stars_invoice(
    payload: CreateInvoiceRequest, user: CurrentUser, session: SessionDep
) -> InvoiceOut:
    return await BillingService(session).create_invoice(user.id, payload.provider)


@router.get("/payments/{payment_id}", response_model=PaymentStatusOut)
async def payment_status(
    payment_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> PaymentStatusOut:
    data = await BillingService(session).payment_status(user.id, payment_id)
    return PaymentStatusOut(**data)


@router.post("/webhooks/telegram")
async def telegram_webhook(
    request: Request,
    session: SessionDep,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    """Telegram payment webhook.

    Secured by the secret token configured with setWebhook, and idempotent: a redelivered
    successful_payment never activates a second subscription.
    """
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise UnauthorizedError("Invalid webhook secret", code="INVALID_WEBHOOK_SECRET")
    elif settings.is_production:
        raise UnauthorizedError("Webhook secret is not configured", code="WEBHOOK_NOT_CONFIGURED")

    body = await request.json()
    provider = PaymentProviderFactory.get(TelegramStarsPaymentProvider.code)
    result = await provider.handle_webhook(body, dict(request.headers))
    if not result.handled:
        return Response(status_code=200)

    service = BillingService(session)

    if result.reason == "pre_checkout_query":
        ok, error = await service.validate_pre_checkout(result)
        if isinstance(provider, TelegramStarsPaymentProvider) and result.external_payment_id:
            try:
                await provider.answer_pre_checkout(result.external_payment_id, ok, error)
            except APIError as exc:
                logger.warning("pre_checkout_answer_failed code=%s", exc.code)
        return Response(status_code=200)

    if result.succeeded:
        try:
            activated = await service.apply_successful_payment(result, provider.code)
            logger.info("telegram_payment_processed activated=%s", activated)
        except APIError as exc:
            # Answer 200 so Telegram stops retrying a payload we will never accept.
            logger.warning("telegram_payment_rejected code=%s", exc.code)
    return Response(status_code=200)
