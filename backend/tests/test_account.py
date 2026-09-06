from __future__ import annotations

from sqlalchemy import func, select

from app.models import (
    AIConversation,
    Book,
    Category,
    Entry,
    EntryEmbedding,
    Tag,
    User,
    UserBook,
    UserIdentity,
)
from tests.conftest import add_book, add_entry


async def _count(session, model, **where) -> int:
    stmt = select(func.count()).select_from(model)
    for column, value in where.items():
        stmt = stmt.where(getattr(model, column) == value)
    return (await session.execute(stmt)).scalar_one()


async def test_profile_and_stats(client, user_a):
    book = await add_book(client, user_a["headers"], "Stats Book")
    await add_entry(client, user_a["headers"], book["id"], type="quote")
    await add_entry(client, user_a["headers"], book["id"], type="note", tags=["тег"])

    me = await client.get("/api/v1/me", headers=user_a["headers"])
    body = me.json()
    assert body["profile"]["first_name"] == "Alice"
    assert body["plan"] == "free"
    assert body["ai_usage"]["limit"] == 3

    stats = await client.get("/api/v1/me/stats", headers=user_a["headers"])
    stats_body = stats.json()
    assert stats_body["books_count"] == 1
    assert stats_body["quotes_count"] == 1
    assert stats_body["notes_count"] == 1
    assert stats_body["entries_count"] == 2
    assert stats_body["tags_count"] == 1


async def test_preferences_round_trip(client, user_a):
    updated = await client.put(
        "/api/v1/me/preferences", json={"theme": "dark"}, headers=user_a["headers"]
    )
    assert updated.json()["theme"] == "dark"

    read = await client.get("/api/v1/me/preferences", headers=user_a["headers"])
    assert read.json()["theme"] == "dark"


async def test_invalid_theme_is_rejected(client, user_a):
    response = await client.put(
        "/api/v1/me/preferences", json={"theme": "neon"}, headers=user_a["headers"]
    )
    assert response.status_code == 422


async def test_onboarding_flag_can_be_set(client, user_a):
    response = await client.patch(
        "/api/v1/me", json={"onboarding_completed": True}, headers=user_a["headers"]
    )
    assert response.json()["onboarding_completed"] is True


async def test_account_deletion_removes_all_user_data(client, user_a, user_b, session):
    book_a = await add_book(client, user_a["headers"], "Alice Only", category="Бизнес")
    await add_entry(client, user_a["headers"], book_a["id"], content="Заметка", tags=["тег"])
    await client.post(
        "/api/v1/ai/conversations", json={"context_type": "all_library"}, headers=user_a["headers"]
    )
    book_b = await add_book(client, user_b["headers"], "Bob Only")
    await add_entry(client, user_b["headers"], book_b["id"], content="Bob note")

    me = await client.get("/api/v1/me", headers=user_a["headers"])
    user_a_id = me.json()["id"]

    deleted = await client.delete("/api/v1/me", headers=user_a["headers"])
    assert deleted.status_code == 200

    import uuid as uuid_module

    uid = uuid_module.UUID(user_a_id)
    assert await _count(session, User, id=uid) == 0
    assert await _count(session, UserIdentity, user_id=uid) == 0
    assert await _count(session, UserBook, user_id=uid) == 0
    assert await _count(session, Entry, user_id=uid) == 0
    assert await _count(session, Tag, user_id=uid) == 0
    assert await _count(session, Category, user_id=uid) == 0
    assert await _count(session, EntryEmbedding, user_id=uid) == 0
    assert await _count(session, AIConversation, user_id=uid) == 0

    # Bob is untouched and the shared catalog survives.
    bob_library = await client.get("/api/v1/library", headers=user_b["headers"])
    assert bob_library.json()["total"] == 1
    assert await _count(session, Book) == 2


async def test_token_of_a_deleted_account_stops_working(client, user_a):
    await client.delete("/api/v1/me", headers=user_a["headers"])
    response = await client.get("/api/v1/me", headers=user_a["headers"])
    assert response.status_code == 401


async def test_shared_catalog_book_is_not_deleted_with_the_account(client, user_a, user_b, session):
    payload = {
        "source": "google_books",
        "source_id": "gb-shared-delete",
        "title": "Shared Forever",
        "isbn_13": "9780000000009",
    }
    await client.post("/api/v1/books", json=payload, headers=user_a["headers"])
    await client.post("/api/v1/books", json=payload, headers=user_b["headers"])

    await client.delete("/api/v1/me", headers=user_a["headers"])

    remaining = await client.get("/api/v1/library", headers=user_b["headers"])
    assert remaining.json()["items"][0]["book"]["title"] == "Shared Forever"


async def test_legal_pages_are_marked_as_placeholders(client):
    for slug in ("privacy", "terms"):
        response = await client.get(f"/api/v1/legal/{slug}")
        assert response.status_code == 200
        assert response.json()["is_placeholder"] is True


async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.json()["status"] == "ok"
