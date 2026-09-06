from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProviderOut(BaseModel):
    code: str
    enabled: bool
    currency: str


class BillingStatusOut(BaseModel):
    plan: str
    is_premium: bool
    status: str
    expires_at: datetime | None = None
    ai_limit: int
    ai_used: int
    ai_remaining: int
    period_end: datetime
    premium_price_stars: int


class CreateInvoiceRequest(BaseModel):
    provider: str = Field("telegram_stars", max_length=32)


class InvoiceOut(BaseModel):
    payment_id: str
    provider: str
    payload: str
    amount: float
    currency: str
    invoice_url: str | None = None
    status: Literal["pending", "succeeded", "failed", "canceled"] = "pending"


class PaymentStatusOut(BaseModel):
    payment_id: str
    status: str
    plan: str
    is_premium: bool
