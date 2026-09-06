"""The critical isolation test: user A must never reach user B's data."""

from __future__ import annotations

from tests.conftest import add_book, add_entry


async def test_user_cannot_read_another_users_book(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Bob's Private Book")

    response = await client.get(f"/api/v1/library/{book_b['id']}", headers=user_a["headers"])
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOK_NOT_FOUND"


async def test_user_cannot_list_another_users_library(client, user_a, user_b):
    await add_book(client, user_b["headers"], "Bob's Book")
    await add_book(client, user_a["headers"], "Alice's Book")

    response = await client.get("/api/v1/library", headers=user_a["headers"])
    titles = [item["book"]["title"] for item in response.json()["items"]]
    assert titles == ["Alice's Book"]


async def test_user_cannot_read_another_users_entry(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Bob's Book")
    entry_b = await add_entry(client, user_b["headers"], book_b["id"], content="Bob's secret quote")

    read = await client.get(f"/api/v1/entries/{entry_b['id']}", headers=user_a["headers"])
    assert read.status_code == 404

    update = await client.patch(
        f"/api/v1/entries/{entry_b['id']}", json={"content": "hacked"}, headers=user_a["headers"]
    )
    assert update.status_code == 404

    delete = await client.delete(f"/api/v1/entries/{entry_b['id']}", headers=user_a["headers"])
    assert delete.status_code == 404

    favorite = await client.put(
        f"/api/v1/entries/{entry_b['id']}/favorite",
        json={"is_favorite": True},
        headers=user_a["headers"],
    )
    assert favorite.status_code == 404

    # ...and the entry is untouched for its owner.
    owner_read = await client.get(f"/api/v1/entries/{entry_b['id']}", headers=user_b["headers"])
    assert owner_read.status_code == 200
    assert owner_read.json()["content"] == "Bob's secret quote"


async def test_user_cannot_write_entries_into_another_users_book(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Bob's Book")
    response = await client.post(
        f"/api/v1/library/{book_b['id']}/entries",
        json={"type": "note", "content": "injected"},
        headers=user_a["headers"],
    )
    assert response.status_code == 404


async def test_user_cannot_modify_another_users_book(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Bob's Book")

    patch = await client.patch(
        f"/api/v1/library/{book_b['id']}",
        json={"is_favorite": True},
        headers=user_a["headers"],
    )
    assert patch.status_code == 404

    delete = await client.delete(f"/api/v1/library/{book_b['id']}", headers=user_a["headers"])
    assert delete.status_code == 404


async def test_search_never_returns_another_users_data(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Secret Manuscript")
    await add_entry(client, user_b["headers"], book_b["id"], content="capital management secrets")

    response = await client.get("/api/v1/search", params={"q": "secret"}, headers=user_a["headers"])
    body = response.json()
    assert body["books"] == []
    assert body["quotes"] == []
    assert body["notes"] == []


async def test_tags_are_scoped_per_user(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Bob's Book")
    await add_entry(client, user_b["headers"], book_b["id"], content="quote", tags=["bobtag"])

    response = await client.get("/api/v1/tags", headers=user_a["headers"])
    assert response.json() == []


async def test_stats_only_count_own_data(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Bob's Book")
    await add_entry(client, user_b["headers"], book_b["id"])

    stats = await client.get("/api/v1/me/stats", headers=user_a["headers"])
    body = stats.json()
    assert body["books_count"] == 0
    assert body["entries_count"] == 0


async def test_ai_conversation_of_another_user_is_not_reachable(client, user_a, user_b):
    created = await client.post(
        "/api/v1/ai/conversations", json={"context_type": "all_library"}, headers=user_b["headers"]
    )
    conversation_id = created.json()["id"]

    read = await client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=user_a["headers"]
    )
    assert read.status_code == 404

    delete = await client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=user_a["headers"]
    )
    assert delete.status_code == 404


async def test_ai_current_book_context_rejects_foreign_book(client, user_a, user_b):
    book_b = await add_book(client, user_b["headers"], "Bob's Book")
    response = await client.post(
        "/api/v1/ai/conversations",
        json={"context_type": "current_book", "context_user_book_id": book_b["id"]},
        headers=user_a["headers"],
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOK_NOT_FOUND"
