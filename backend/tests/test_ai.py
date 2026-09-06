from __future__ import annotations

import json

from app.integrations.ai import LLMResponse, set_providers
from app.integrations.ai.base import ChatMessage, LLMProvider
from tests.conftest import add_book, add_entry


class ScriptedLLM(LLMProvider):
    """Returns a fixed envelope so source validation can be tested precisely."""

    def __init__(self, answer: str, source_ids: list[str]) -> None:
        self.model = "scripted"
        self.answer = answer
        self.source_ids = source_ids
        self.calls: list[list[ChatMessage]] = []

    async def complete(self, messages, *, temperature=0.2, max_tokens=1200, json_mode=False):
        self.calls.append(messages)
        return LLMResponse(
            content=json.dumps({"answer": self.answer, "source_ids": self.source_ids})
        )


class FailingLLM(LLMProvider):
    model = "failing"

    async def complete(self, messages, *, temperature=0.2, max_tokens=1200, json_mode=False):
        from app.core.errors import ProviderError

        raise ProviderError("provider is down")


async def _library_with_entries(client, headers):
    book = await add_book(client, headers, "Psychology of Money", authors=["Morgan Housel"])
    quote = await add_entry(
        client,
        headers,
        book["id"],
        type="quote",
        content="Управление капиталом важнее доходности инвестиций.",
        chapter="4",
        tags=["деньги"],
    )
    return book, quote


async def test_ai_answers_from_the_users_own_library(client, user_a):
    book, quote = await _library_with_entries(client, user_a["headers"])

    response = await client.post(
        "/api/v1/ai/ask",
        json={"question": "Что я сохранял про управление капиталом?"},
        headers=user_a["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    source_ids = [s["entry_id"] for s in body["message"]["sources"]]
    assert quote["id"] in source_ids
    source = body["message"]["sources"][0]
    assert source["book_title"] == "Psychology of Money"
    assert source["user_book_id"] == book["id"]
    assert source["entry_type"] == "quote"
    assert source["chapter"] == "4"
    assert source["snippet"]


async def test_ai_context_never_includes_another_users_entries(client, user_a, user_b, fake_llm):
    await _library_with_entries(client, user_b["headers"])
    # Alice has her own library on an unrelated topic.
    book_a = await add_book(client, user_a["headers"], "Cooking")
    await add_entry(client, user_a["headers"], book_a["id"], content="Как варить борщ")

    response = await client.post(
        "/api/v1/ai/ask",
        json={"question": "управление капиталом"},
        headers=user_a["headers"],
    )
    body = response.json()
    for source in body["message"]["sources"]:
        assert source["user_book_id"] == book_a["id"]

    # And nothing from Bob's library reached the prompt.
    prompts = "\n".join(m.content for call in fake_llm.calls for m in call)
    assert "Psychology of Money" not in prompts


async def test_empty_library_returns_not_enough_context(client, user_a):
    response = await client.post(
        "/api/v1/ai/ask", json={"question": "Что я читал про деньги?"}, headers=user_a["headers"]
    )
    body = response.json()
    assert body["status"] == "not_enough_context"
    assert body["message"]["sources"] == []
    # Nothing was charged, because no LLM call happened.
    assert body["usage"]["used"] == 0


async def test_unknown_source_ids_from_the_llm_are_dropped(client, user_a):
    _book, quote = await _library_with_entries(client, user_a["headers"])
    set_providers(
        llm=ScriptedLLM(
            "Ответ",
            ["00000000-0000-0000-0000-000000000000", quote["id"]],
        )
    )

    response = await client.post(
        "/api/v1/ai/ask", json={"question": "управление капиталом"}, headers=user_a["headers"]
    )
    source_ids = [s["entry_id"] for s in response.json()["message"]["sources"]]
    assert source_ids == [quote["id"]]


async def test_quota_is_enforced_server_side(client, user_a):
    await _library_with_entries(client, user_a["headers"])

    # FREE_AI_REQUESTS_PER_MONTH is 3 in the test environment.
    for index in range(3):
        response = await client.post(
            "/api/v1/ai/ask", json={"question": "управление капиталом"}, headers=user_a["headers"]
        )
        assert response.status_code == 200
        assert response.json()["usage"]["remaining"] == 2 - index

    blocked = await client.post(
        "/api/v1/ai/ask", json={"question": "управление капиталом"}, headers=user_a["headers"]
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "AI_LIMIT_REACHED"


async def test_provider_failure_does_not_consume_quota(client, user_a):
    await _library_with_entries(client, user_a["headers"])
    set_providers(llm=FailingLLM())

    failed = await client.post(
        "/api/v1/ai/ask", json={"question": "управление капиталом"}, headers=user_a["headers"]
    )
    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "PROVIDER_ERROR"

    usage = await client.get("/api/v1/ai/usage", headers=user_a["headers"])
    assert usage.json()["used"] == 0
    assert usage.json()["limit"] == 3


async def test_usage_limit_comes_from_the_backend(client, user_a):
    usage = await client.get("/api/v1/ai/usage", headers=user_a["headers"])
    body = usage.json()
    assert body["plan"] == "free"
    assert body["limit"] == 3
    assert body["remaining"] == 3
    assert body["period_end"]


async def test_current_book_context_restricts_retrieval(client, user_a, fake_llm):
    book_money, _quote = await _library_with_entries(client, user_a["headers"])
    book_habits = await add_book(client, user_a["headers"], "Atomic Habits")
    await add_entry(
        client,
        user_a["headers"],
        book_habits["id"],
        content="Управление капиталом привычек начинается с малого.",
    )

    response = await client.post(
        "/api/v1/ai/ask",
        json={
            "question": "управление капиталом",
            "context_type": "current_book",
            "context_user_book_id": book_money["id"],
        },
        headers=user_a["headers"],
    )
    sources = response.json()["message"]["sources"]
    assert sources
    assert all(s["user_book_id"] == book_money["id"] for s in sources)


async def test_favorites_context_only_uses_favorites(client, user_a):
    book = await add_book(client, user_a["headers"], "Mixed Book")
    plain = await add_entry(
        client, user_a["headers"], book["id"], content="Обычная запись про капитал"
    )
    starred = await add_entry(
        client, user_a["headers"], book["id"], content="Избранная запись про капитал"
    )
    await client.put(
        f"/api/v1/entries/{starred['id']}/favorite",
        json={"is_favorite": True},
        headers=user_a["headers"],
    )

    response = await client.post(
        "/api/v1/ai/ask",
        json={"question": "капитал", "context_type": "favorites"},
        headers=user_a["headers"],
    )
    source_ids = [s["entry_id"] for s in response.json()["message"]["sources"]]
    assert starred["id"] in source_ids
    assert plain["id"] not in source_ids


async def test_conversation_history_is_stored_and_retrievable(client, user_a):
    await _library_with_entries(client, user_a["headers"])

    first = await client.post(
        "/api/v1/ai/ask", json={"question": "управление капиталом"}, headers=user_a["headers"]
    )
    conversation_id = first.json()["conversation_id"]

    follow_up = await client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"question": "а что ещё про деньги?"},
        headers=user_a["headers"],
    )
    assert follow_up.json()["conversation_id"] == conversation_id

    detail = await client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=user_a["headers"]
    )
    roles = [m["role"] for m in detail.json()["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert detail.json()["messages"][1]["sources"]

    listing = await client.get("/api/v1/ai/conversations", headers=user_a["headers"])
    assert listing.json()["total"] == 1

    deleted = await client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=user_a["headers"]
    )
    assert deleted.status_code == 200
    assert (await client.get("/api/v1/ai/conversations", headers=user_a["headers"])).json()[
        "total"
    ] == 0


async def test_question_length_is_validated(client, user_a):
    response = await client.post(
        "/api/v1/ai/ask", json={"question": "x" * 1001}, headers=user_a["headers"]
    )
    assert response.status_code == 422


async def test_current_book_context_requires_a_book_id(client, user_a):
    response = await client.post(
        "/api/v1/ai/conversations",
        json={"context_type": "current_book"},
        headers=user_a["headers"],
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_CONTEXT"
