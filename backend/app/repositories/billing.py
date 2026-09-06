from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import ensure_utc
from app.models import Payment, PaymentStatus, Plan, Subscription, SubscriptionStatus


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_plan(self, code: str) -> Plan | None:
        stmt = select(Plan).where(Plan.code == code)
        return (await self.session.execute(stmt)).scalars().first()

    async def ensure_plan(self, code: str, name: str, ai_limit: int) -> Plan:
        plan = await self.get_plan(code)
        if plan is None:
            plan = Plan(code=code, name=name, ai_limit=ai_limit)
            self.session.add(plan)
            await self.session.flush()
        return plan

    async def active_subscription(self, user_id: uuid.UUID, now: datetime) -> Subscription | None:
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.active,
            )
            .order_by(Subscription.expires_at.desc().nullslast())
        )
        for subscription in (await self.session.execute(stmt)).scalars().all():
            expires_at = ensure_utc(subscription.expires_at)
            if expires_at is None or expires_at > ensure_utc(now):
                return subscription
        return None

    async def latest_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def create_subscription(self, **fields) -> Subscription:
        subscription = Subscription(**fields)
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def create_payment(self, **fields) -> Payment:
        payment = Payment(**fields)
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_payment(self, payment_id: uuid.UUID) -> Payment | None:
        return await self.session.get(Payment, payment_id)

    async def get_payment_by_payload(self, payload: str) -> Payment | None:
        stmt = select(Payment).where(Payment.payload == payload)
        return (await self.session.execute(stmt)).scalars().first()

    async def get_payment_by_external_id(
        self, provider: str, external_payment_id: str
    ) -> Payment | None:
        stmt = select(Payment).where(
            Payment.provider == provider, Payment.external_payment_id == external_payment_id
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def user_payments(self, user_id: uuid.UUID, limit: int = 20) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def mark_payment(self, payment: Payment, status: PaymentStatus, **fields) -> Payment:
        payment.status = status
        for key, value in fields.items():
            setattr(payment, key, value)
        await self.session.flush()
        return payment
