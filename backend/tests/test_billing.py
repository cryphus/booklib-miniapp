from __future__ import annotations

from app.integrations.payments import PaymentProviderFactory
from app.integrations.payments.base import PaymentIntent
from app.integrations.payments.telegram_stars import TelegramStarsPaymentProvider
from app.services.billing_service import BillingService
from tests.conftest import add_book, add_entry

STARS_PRICE = 250


class FakeStarsProvider(TelegramStarsPaymentProvider):
    """Same adapter, with the two Telegram Bot API calls stubbed out."""

    def __init__(self) -> None:
        super().__init__()
        self.pre_checkout_answers: list[tuple[str, bool, str | None]] = []

    @property
    def enabled(self) -> bool:
        return True

    async def create_payment(self, *, payload, amount, description, title, user_meta):
        return PaymentIntent(
            provider=self.code,
            payload=payload,
            amount=amount,
            currency=self.currency,
            invoice_url=f"https://t.me/invoice/{payload}",
        )

    async def answer_pre_checkout(self, query_id, ok, error=None):
        self.pre_checkout_answers.append((query_id, ok, error))


def _successful_payment_update(payload: str, charge_id: str, amount: int = STARS_PRICE) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "successful_payment": {
                "currency": "XTR",
                "total_amount": amount,
                "invoice_payload": payload,
                "telegram_payment_charge_id": charge_id,
                "provider_payment_charge_id": "prov-1",
            },
        },
    }


async def _create_invoice(client, headers) -> dict:
    response = await client.post(
        "/api/v1/billing/telegram-stars/create",
        json={"provider": "telegram_stars"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_providers_endpoint_reports_backend_flags(client):
    response = await client.get("/api/v1/billing/providers")
    providers = {p["code"]: p for p in response.json()}
    assert set(providers) == {"telegram_stars", "yookassa", "platega", "cryptobot"}
    assert providers["yookassa"]["enabled"] is False
    assert providers["platega"]["enabled"] is False
    assert providers["cryptobot"]["enabled"] is False


async def test_disabled_provider_refuses_without_faking_success(client, user_a):
    response = await client.post(
        "/api/v1/billing/telegram-stars/create",
        json={"provider": "yookassa"},
        headers=user_a["headers"],
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PAYMENT_PROVIDER_NOT_CONFIGURED"


async def test_new_user_starts_on_free_plan(client, user_a):
    status = await client.get("/api/v1/billing/status", headers=user_a["headers"])
    body = status.json()
    assert body["plan"] == "free"
    assert body["is_premium"] is False
    assert body["premium_price_stars"] == STARS_PRICE


async def test_stars_payment_activates_premium(client, user_a):
    provider = FakeStarsProvider()
    PaymentProviderFactory.override("telegram_stars", provider)

    invoice = await _create_invoice(client, user_a["headers"])
    assert invoice["currency"] == "XTR"
    assert invoice["amount"] == STARS_PRICE
    assert invoice["invoice_url"].startswith("https://t.me/invoice/")

    webhook = await client.post(
        "/api/v1/billing/webhooks/telegram",
        json=_successful_payment_update(invoice["payload"], "charge-1"),
    )
    assert webhook.status_code == 200

    status = await client.get("/api/v1/billing/status", headers=user_a["headers"])
    body = status.json()
    assert body["plan"] == "premium"
    assert body["is_premium"] is True
    assert body["expires_at"] is not None

    me = await client.get("/api/v1/me", headers=user_a["headers"])
    assert me.json()["is_premium"] is True
    assert me.json()["ai_usage"]["limit"] == 100  # premium limit from the test env

    payment_status = await client.get(
        f"/api/v1/billing/payments/{invoice['payment_id']}", headers=user_a["headers"]
    )
    assert payment_status.json()["status"] == "succeeded"


async def test_webhook_redelivery_is_idempotent(client, user_a, session):
    PaymentProviderFactory.override("telegram_stars", FakeStarsProvider())
    invoice = await _create_invoice(client, user_a["headers"])
    update = _successful_payment_update(invoice["payload"], "charge-repeat")

    for _ in range(3):
        assert (
            await client.post("/api/v1/billing/webhooks/telegram", json=update)
        ).status_code == 200

    me = await client.get("/api/v1/me", headers=user_a["headers"])
    user_id = me.json()["id"]

    from sqlalchemy import func, select

    from app.models import Subscription

    count = (
        await session.execute(
            select(func.count()).select_from(Subscription).where(Subscription.user_id == user_id)
        )
    ).scalar_one()
    assert count == 1

    status = await client.get("/api/v1/billing/status", headers=user_a["headers"])
    assert status.json()["is_premium"] is True


async def test_amount_mismatch_does_not_grant_premium(client, user_a):
    PaymentProviderFactory.override("telegram_stars", FakeStarsProvider())
    invoice = await _create_invoice(client, user_a["headers"])

    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json=_successful_payment_update(invoice["payload"], "charge-cheap", amount=1),
    )

    status = await client.get("/api/v1/billing/status", headers=user_a["headers"])
    assert status.json()["is_premium"] is False


async def test_unknown_payload_does_not_grant_premium(client, user_a):
    PaymentProviderFactory.override("telegram_stars", FakeStarsProvider())
    await _create_invoice(client, user_a["headers"])

    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json=_successful_payment_update("premium:someone-else:forged", "charge-forged"),
    )

    status = await client.get("/api/v1/billing/status", headers=user_a["headers"])
    assert status.json()["is_premium"] is False


async def test_pre_checkout_is_answered_for_a_valid_invoice(client, user_a):
    provider = FakeStarsProvider()
    PaymentProviderFactory.override("telegram_stars", provider)
    invoice = await _create_invoice(client, user_a["headers"])

    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json={
            "update_id": 2,
            "pre_checkout_query": {
                "id": "pcq-1",
                "currency": "XTR",
                "total_amount": STARS_PRICE,
                "invoice_payload": invoice["payload"],
            },
        },
    )
    assert provider.pre_checkout_answers == [("pcq-1", True, None)]


async def test_pre_checkout_is_rejected_for_an_unknown_payload(client, user_a):
    provider = FakeStarsProvider()
    PaymentProviderFactory.override("telegram_stars", provider)

    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json={
            "update_id": 3,
            "pre_checkout_query": {
                "id": "pcq-2",
                "currency": "XTR",
                "total_amount": STARS_PRICE,
                "invoice_payload": "premium:unknown:nope",
            },
        },
    )
    query_id, ok, error = provider.pre_checkout_answers[0]
    assert (query_id, ok) == ("pcq-2", False)
    assert error


async def test_premium_raises_the_ai_limit(client, user_a):
    PaymentProviderFactory.override("telegram_stars", FakeStarsProvider())
    book = await add_book(client, user_a["headers"], "Money Book")
    await add_entry(client, user_a["headers"], book["id"], content="Заметка про капитал")

    for _ in range(3):
        await client.post(
            "/api/v1/ai/ask", json={"question": "капитал"}, headers=user_a["headers"]
        )
    blocked = await client.post(
        "/api/v1/ai/ask", json={"question": "капитал"}, headers=user_a["headers"]
    )
    assert blocked.status_code == 403

    invoice = await _create_invoice(client, user_a["headers"])
    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json=_successful_payment_update(invoice["payload"], "charge-upgrade"),
    )

    allowed = await client.post(
        "/api/v1/ai/ask", json={"question": "капитал"}, headers=user_a["headers"]
    )
    assert allowed.status_code == 200
    assert allowed.json()["usage"]["plan"] == "premium"
    assert allowed.json()["usage"]["limit"] == 100


async def test_second_purchase_extends_the_same_subscription(client, user_a, session):
    PaymentProviderFactory.override("telegram_stars", FakeStarsProvider())

    first = await _create_invoice(client, user_a["headers"])
    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json=_successful_payment_update(first["payload"], "charge-a"),
    )
    status_one = await client.get("/api/v1/billing/status", headers=user_a["headers"])

    second = await _create_invoice(client, user_a["headers"])
    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json=_successful_payment_update(second["payload"], "charge-b"),
    )
    status_two = await client.get("/api/v1/billing/status", headers=user_a["headers"])

    assert status_two.json()["expires_at"] > status_one.json()["expires_at"]


async def test_month_period_boundaries(session):
    from datetime import datetime, timezone

    from app.services.billing_service import month_period

    start, end = month_period(datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 2, 1, tzinfo=timezone.utc)

    start, end = month_period(datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc))
    assert end == datetime(2027, 1, 1, tzinfo=timezone.utc)


async def test_ensure_plans_is_idempotent(session):
    service = BillingService(session)
    await service.ensure_plans()
    await service.ensure_plans()

    from sqlalchemy import func, select

    from app.models import Plan

    count = (await session.execute(select(func.count()).select_from(Plan))).scalar_one()
    assert count == 2
