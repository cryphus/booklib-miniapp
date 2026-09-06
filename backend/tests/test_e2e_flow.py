"""End-to-end walk through the Definition of Done, over the real HTTP API.

Every step a user performs in the Mini App, in order, with only the AI provider and the
Telegram Bot API stubbed out (no network calls in tests).
"""

from __future__ import annotations

from app.integrations.payments import PaymentProviderFactory
from app.integrations.payments.base import PaymentIntent
from app.integrations.payments.telegram_stars import TelegramStarsPaymentProvider


class StarsProviderStub(TelegramStarsPaymentProvider):
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
        return None


async def test_full_user_journey(client):
    # 1-2. authenticate
    auth = await client.post("/api/v1/auth/dev", json={"telegram_id": 424242, "first_name": "Мария"})
    assert auth.status_code == 200
    headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}
    assert auth.json()["is_new_user"] is True

    # 3. empty library
    library = await client.get("/api/v1/library", headers=headers)
    assert library.json()["total"] == 0

    # 4-6. add a catalog book and a manual one
    catalog = await client.post(
        "/api/v1/books",
        json={
            "source": "google_books",
            "source_id": "gb-psychology",
            "title": "Психология денег",
            "authors": ["Морган Хаузел"],
            "isbn_13": "9780857197689",
            "category": "Финансы",
        },
        headers=headers,
    )
    assert catalog.status_code == 201
    book_id = catalog.json()["id"]

    manual = await client.post(
        "/api/v1/books/manual",
        json={"title": "Мои конспекты", "authors": ["Я"], "category": "Личное"},
        headers=headers,
    )
    assert manual.status_code == 201

    # 7. open the book
    detail = await client.get(f"/api/v1/library/{book_id}", headers=headers)
    assert detail.json()["book"]["title"] == "Психология денег"

    # 8-10. a quote and a note, both tagged
    quote = await client.post(
        f"/api/v1/library/{book_id}/entries",
        json={
            "type": "quote",
            "content": "Управление капиталом важнее доходности инвестиций.",
            "personal_note": "Проверить на своём портфеле.",
            "chapter": "4",
            "page": "88",
            "tags": ["деньги", "Инвестиции"],
        },
        headers=headers,
    )
    assert quote.status_code == 201
    quote_id = quote.json()["id"]

    note = await client.post(
        f"/api/v1/library/{book_id}/entries",
        json={"type": "note", "content": "Моя мысль про капитал и терпение.", "tags": ["деньги"]},
        headers=headers,
    )
    assert note.status_code == 201

    tags = await client.get("/api/v1/tags", headers=headers)
    assert {t["name"] for t in tags.json()} == {"деньги", "Инвестиции"}

    # 11. edit
    edited = await client.patch(
        f"/api/v1/entries/{quote_id}",
        json={"content": "Управление капиталом важнее доходности.", "tags": ["деньги"]},
        headers=headers,
    )
    assert edited.json()["content"] == "Управление капиталом важнее доходности."

    # 13. favorites
    await client.put(f"/api/v1/entries/{quote_id}/favorite", json={"is_favorite": True}, headers=headers)
    await client.patch(f"/api/v1/library/{book_id}", json={"is_favorite": True}, headers=headers)
    favorites = await client.get("/api/v1/library", params={"favorite": True}, headers=headers)
    assert favorites.json()["total"] == 1

    # 14. search
    search = await client.get("/api/v1/search", params={"q": "капитал"}, headers=headers)
    body = search.json()
    assert body["total"] >= 2
    # the frontend navigates with these two ids
    assert body["quotes"][0]["user_book_id"] == book_id

    # 15-19. ask the AI and follow a source back to its entry
    answer = await client.post(
        "/api/v1/ai/ask",
        json={"question": "Что я сохранял про управление капиталом?"},
        headers=headers,
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["status"] == "ok"
    source = payload["message"]["sources"][0]
    assert source["user_book_id"] == book_id
    entry = await client.get(f"/api/v1/entries/{source['entry_id']}", headers=headers)
    assert entry.status_code == 200
    assert payload["usage"]["used"] == 1
    assert payload["usage"]["remaining"] == payload["usage"]["limit"] - 1

    # 20. the limit blocks further requests (FREE_AI_REQUESTS_PER_MONTH is 3 in tests)
    for _ in range(2):
        await client.post("/api/v1/ai/ask", json={"question": "капитал"}, headers=headers)
    blocked = await client.post("/api/v1/ai/ask", json={"question": "капитал"}, headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "AI_LIMIT_REACHED"

    # 21-24. buy Premium with Telegram Stars and see it in the profile
    PaymentProviderFactory.override("telegram_stars", StarsProviderStub())
    invoice = await client.post(
        "/api/v1/billing/telegram-stars/create", json={"provider": "telegram_stars"}, headers=headers
    )
    assert invoice.status_code == 200
    assert invoice.json()["currency"] == "XTR"

    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json={
            "update_id": 7,
            "pre_checkout_query": {
                "id": "pcq-e2e",
                "currency": "XTR",
                "total_amount": invoice.json()["amount"],
                "invoice_payload": invoice.json()["payload"],
            },
        },
    )
    await client.post(
        "/api/v1/billing/webhooks/telegram",
        json={
            "update_id": 8,
            "message": {
                "message_id": 1,
                "successful_payment": {
                    "currency": "XTR",
                    "total_amount": invoice.json()["amount"],
                    "invoice_payload": invoice.json()["payload"],
                    "telegram_payment_charge_id": "charge-e2e",
                },
            },
        },
    )

    me = await client.get("/api/v1/me", headers=headers)
    assert me.json()["is_premium"] is True
    assert me.json()["plan"] == "premium"

    # AI works again on the higher limit
    after_premium = await client.post(
        "/api/v1/ai/ask", json={"question": "капитал"}, headers=headers
    )
    assert after_premium.status_code == 200

    # 25. conversation history
    history = await client.get("/api/v1/ai/conversations", headers=headers)
    assert history.json()["total"] >= 1

    # 26. settings
    preferences = await client.put(
        "/api/v1/me/preferences", json={"theme": "dark"}, headers=headers
    )
    assert preferences.json()["theme"] == "dark"

    # 12. delete an entry
    deleted = await client.delete(f"/api/v1/entries/{quote_id}", headers=headers)
    assert deleted.status_code == 200

    # 27. delete the account
    removed = await client.delete("/api/v1/me", headers=headers)
    assert removed.status_code == 200
    assert (await client.get("/api/v1/me", headers=headers)).status_code == 401
