from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    ConflictError,
    NotFoundError,
    PaymentProviderNotConfiguredError,
    ValidationError,
)
from app.core.logging import logger
from app.db.base import ensure_utc
from app.integrations.payments import PaymentProviderFactory
from app.integrations.payments.base import WebhookResult
from app.models import (
    Payment,
    PaymentStatus,
    PlanCode,
    Subscription,
    SubscriptionStatus,
)
from app.repositories import AIRepository, BillingRepository
from app.schemas.billing import BillingStatusOut, InvoiceOut, ProviderOut

PREMIUM_TITLE = "Remarka Premium"
PREMIUM_DESCRIPTION = "Premium subscription for Remarka: expanded AI limits."


@dataclass
class AIQuota:
    plan: str
    used: int
    limit: int
    remaining: int
    period_start: datetime
    period_end: datetime


def month_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Calendar-month window used for AI quota accounting."""
    now = now or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, end


class BillingService:
    """Single source of truth for plan, quota and payments. The frontend never decides these."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.billing = BillingRepository(session)
        self.ai = AIRepository(session)

    # ---------- plans ----------

    async def ensure_plans(self) -> None:
        await self.billing.ensure_plan(
            PlanCode.free.value, "Free", settings.FREE_AI_REQUESTS_PER_MONTH
        )
        await self.billing.ensure_plan(
            PlanCode.premium.value, "Premium", settings.PREMIUM_AI_REQUESTS_PER_MONTH
        )

    async def current_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        return await self.billing.active_subscription(user_id, datetime.now(timezone.utc))

    async def current_plan_code(self, user_id: uuid.UUID) -> str:
        subscription = await self.current_subscription(user_id)
        if subscription is None:
            return PlanCode.free.value
        return subscription.plan.code

    async def is_premium(self, user_id: uuid.UUID) -> bool:
        return await self.current_plan_code(user_id) == PlanCode.premium.value

    async def plan_limit(self, plan_code: str) -> int:
        plan = await self.billing.get_plan(plan_code)
        if plan is not None:
            return plan.ai_limit
        return (
            settings.PREMIUM_AI_REQUESTS_PER_MONTH
            if plan_code == PlanCode.premium.value
            else settings.FREE_AI_REQUESTS_PER_MONTH
        )

    # ---------- AI quota ----------

    async def get_ai_quota(self, user_id: uuid.UUID) -> AIQuota:
        plan_code = await self.current_plan_code(user_id)
        limit = await self.plan_limit(plan_code)
        period_start, period_end = month_period()
        usage = await self.ai.get_usage(user_id, period_start)
        used = usage.used if usage else 0
        return AIQuota(
            plan=plan_code,
            used=used,
            limit=limit,
            remaining=max(limit - used, 0),
            period_start=period_start,
            period_end=period_end,
        )

    async def consume_ai_request(self, user_id: uuid.UUID) -> AIQuota:
        period_start, period_end = month_period()
        usage = await self.ai.get_usage(user_id, period_start)
        if usage is None:
            usage = await self.ai.create_usage(user_id, period_start, period_end)
        usage.used += 1
        await self.session.flush()
        return await self.get_ai_quota(user_id)

    # ---------- status / providers ----------

    async def status(self, user_id: uuid.UUID) -> BillingStatusOut:
        subscription = await self.current_subscription(user_id)
        quota = await self.get_ai_quota(user_id)
        return BillingStatusOut(
            plan=quota.plan,
            is_premium=quota.plan == PlanCode.premium.value,
            status=subscription.status.value if subscription else "none",
            expires_at=subscription.expires_at if subscription else None,
            ai_limit=quota.limit,
            ai_used=quota.used,
            ai_remaining=quota.remaining,
            period_end=quota.period_end,
            premium_price_stars=settings.TELEGRAM_PREMIUM_PRICE_STARS,
        )

    @staticmethod
    def providers() -> list[ProviderOut]:
        return [
            ProviderOut(code=p.code, enabled=p.enabled, currency=p.currency)
            for p in PaymentProviderFactory.all()
        ]

    # ---------- payments ----------

    async def create_invoice(self, user_id: uuid.UUID, provider_code: str) -> InvoiceOut:
        provider = PaymentProviderFactory.get(provider_code)
        if not provider.enabled:
            raise PaymentProviderNotConfiguredError(
                f"Payment provider '{provider_code}' is not available yet"
            )

        amount = float(settings.TELEGRAM_PREMIUM_PRICE_STARS)
        payload = f"premium:{user_id}:{secrets.token_urlsafe(12)}"

        payment = await self.billing.create_payment(
            user_id=user_id,
            provider=provider.code,
            payload=payload,
            amount=amount,
            currency=provider.currency,
            status=PaymentStatus.pending,
            meta={"plan": PlanCode.premium.value},
        )

        intent = await provider.create_payment(
            payload=payload,
            amount=amount,
            title=PREMIUM_TITLE,
            description=PREMIUM_DESCRIPTION,
            user_meta={"user_id": str(user_id)},
        )
        if intent.external_payment_id:
            payment.external_payment_id = intent.external_payment_id
        payment.meta = {**(payment.meta or {}), "invoice_url": intent.invoice_url}
        await self.session.flush()

        return InvoiceOut(
            payment_id=str(payment.id),
            provider=provider.code,
            payload=payload,
            amount=intent.amount,
            currency=intent.currency,
            invoice_url=intent.invoice_url,
            status="pending",
        )

    async def payment_status(self, user_id: uuid.UUID, payment_id: uuid.UUID) -> dict:
        payment = await self.billing.get_payment(payment_id)
        if payment is None or payment.user_id != user_id:
            raise NotFoundError("Payment not found", code="PAYMENT_NOT_FOUND")
        plan_code = await self.current_plan_code(user_id)
        return {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "plan": plan_code,
            "is_premium": plan_code == PlanCode.premium.value,
        }

    # ---------- webhooks ----------

    async def validate_pre_checkout(self, result: WebhookResult) -> tuple[bool, str | None]:
        """Answers the Telegram pre_checkout_query only if payload and amount still match."""
        if not result.payload:
            return False, "Invalid payment payload"
        payment = await self.billing.get_payment_by_payload(result.payload)
        if payment is None:
            return False, "Unknown payment"
        if payment.status == PaymentStatus.succeeded:
            return False, "This invoice has already been paid"
        if result.amount is not None and float(payment.amount) != float(result.amount):
            logger.warning("payment_amount_mismatch payload=%s", result.payload[:24])
            return False, "Payment amount mismatch"
        if result.currency and result.currency != payment.currency:
            return False, "Payment currency mismatch"
        return True, None

    async def apply_successful_payment(self, result: WebhookResult, provider_code: str) -> bool:
        """Idempotent. A redelivered webhook never creates a second subscription."""
        if not result.payload:
            raise ValidationError("Webhook payload is missing", code="INVALID_WEBHOOK")

        payment = await self.billing.get_payment_by_payload(result.payload)
        if payment is None:
            raise NotFoundError("Unknown payment payload", code="PAYMENT_NOT_FOUND")
        if payment.provider != provider_code:
            raise ValidationError("Payment provider mismatch", code="INVALID_WEBHOOK")

        if payment.status == PaymentStatus.succeeded:
            logger.info("payment_webhook_duplicate payment_id=%s", payment.id)
            return False

        if result.amount is not None and float(payment.amount) != float(result.amount):
            await self.billing.mark_payment(payment, PaymentStatus.failed)
            raise ValidationError("Payment amount mismatch", code="PAYMENT_AMOUNT_MISMATCH")
        if result.currency and result.currency != payment.currency:
            await self.billing.mark_payment(payment, PaymentStatus.failed)
            raise ValidationError("Payment currency mismatch", code="PAYMENT_CURRENCY_MISMATCH")

        if result.external_payment_id:
            existing = await self.billing.get_payment_by_external_id(
                provider_code, result.external_payment_id
            )
            if existing is not None and existing.id != payment.id:
                raise ConflictError("Charge already processed", code="PAYMENT_ALREADY_PROCESSED")

        await self.billing.mark_payment(
            payment,
            PaymentStatus.succeeded,
            external_payment_id=result.external_payment_id,
        )
        await self.activate_premium(payment.user_id, provider_code, result.external_payment_id)
        return True

    async def activate_premium(
        self,
        user_id: uuid.UUID,
        provider_code: str,
        provider_subscription_id: str | None = None,
    ) -> Subscription:
        """Extends an active premium subscription instead of stacking a second one."""
        await self.ensure_plans()
        plan = await self.billing.get_plan(PlanCode.premium.value)
        now = datetime.now(timezone.utc)
        period = timedelta(days=settings.PREMIUM_PERIOD_DAYS)

        current = await self.billing.active_subscription(user_id, now)
        if current is not None and current.plan.code == PlanCode.premium.value:
            expires_at = ensure_utc(current.expires_at)
            base = expires_at if expires_at and expires_at > now else now
            current.expires_at = base + period
            current.provider_subscription_id = (
                provider_subscription_id or current.provider_subscription_id
            )
            await self.session.flush()
            return current

        return await self.billing.create_subscription(
            user_id=user_id,
            plan_id=plan.id,
            provider=provider_code,
            provider_subscription_id=provider_subscription_id,
            status=SubscriptionStatus.active,
            starts_at=now,
            expires_at=now + period,
        )

    async def user_payments(self, user_id: uuid.UUID) -> list[Payment]:
        return await self.billing.user_payments(user_id)
