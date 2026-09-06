from __future__ import annotations

from app.repositories.tags import normalize_tag
from tests.conftest import add_book, add_entry


async def test_quote_crud_round_trip(client, user_a):
    book = await add_book(client, user_a["headers"], "Psychology of Money")

    created = await add_entry(
        client,
        user_a["headers"],
        book["id"],
        type="quote",
        content="Wealth is what you do not see.",
        personal_note="Worth remembering.",
        chapter="2",
        page="41",
        tags=["деньги", "долгосрочность"],
    )
    assert created["type"] == "quote"
    assert created["personal_note"] == "Worth remembering."
    assert created["chapter"] == "2"
    assert {t["name"] for t in created["tags"]} == {"деньги", "долгосрочность"}
    assert created["book"]["title"] == "Psychology of Money"

    updated = await client.patch(
        f"/api/v1/entries/{created['id']}",
        json={"content": "Wealth is hidden.", "tags": ["деньги"]},
        headers=user_a["headers"],
    )
    assert updated.json()["content"] == "Wealth is hidden."
    assert [t["name"] for t in updated.json()["tags"]] == ["деньги"]

    favorite = await client.put(
        f"/api/v1/entries/{created['id']}/favorite",
        json={"is_favorite": True},
        headers=user_a["headers"],
    )
    assert favorite.json()["is_favorite"] is True

    deleted = await client.delete(f"/api/v1/entries/{created['id']}", headers=user_a["headers"])
    assert deleted.status_code == 200

    gone = await client.get(f"/api/v1/entries/{created['id']}", headers=user_a["headers"])
    assert gone.status_code == 404


async def test_note_has_no_personal_note(client, user_a):
    book = await add_book(client, user_a["headers"])
    note = await add_entry(
        client,
        user_a["headers"],
        book["id"],
        type="note",
        content="My own thought about the chapter.",
        personal_note="should be ignored for notes",
    )
    assert note["type"] == "note"
    assert note["personal_note"] is None


async def test_entries_are_filtered_by_type_and_favorite(client, user_a):
    book = await add_book(client, user_a["headers"])
    await add_entry(client, user_a["headers"], book["id"], type="quote", content="A quote")
    note = await add_entry(client, user_a["headers"], book["id"], type="note", content="A note")
    await client.put(
        f"/api/v1/entries/{note['id']}/favorite",
        json={"is_favorite": True},
        headers=user_a["headers"],
    )

    quotes = await client.get(
        f"/api/v1/library/{book['id']}/entries", params={"type": "quote"}, headers=user_a["headers"]
    )
    assert [e["content"] for e in quotes.json()["items"]] == ["A quote"]

    favorites = await client.get(
        f"/api/v1/library/{book['id']}/entries",
        params={"favorite": True},
        headers=user_a["headers"],
    )
    assert [e["content"] for e in favorites.json()["items"]] == ["A note"]


async def test_book_entry_counts_are_reported(client, user_a):
    book = await add_book(client, user_a["headers"])
    await add_entry(client, user_a["headers"], book["id"], type="quote")
    await add_entry(client, user_a["headers"], book["id"], type="quote")
    await add_entry(client, user_a["headers"], book["id"], type="note")

    detail = await client.get(f"/api/v1/library/{book['id']}", headers=user_a["headers"])
    body = detail.json()
    assert body["quotes_count"] == 2
    assert body["notes_count"] == 1
    assert body["entries_count"] == 3


async def test_empty_content_is_rejected(client, user_a):
    book = await add_book(client, user_a["headers"])
    response = await client.post(
        f"/api/v1/library/{book['id']}/entries",
        json={"type": "quote", "content": "   "},
        headers=user_a["headers"],
    )
    assert response.status_code == 422


async def test_oversized_content_is_rejected(client, user_a):
    book = await add_book(client, user_a["headers"])
    response = await client.post(
        f"/api/v1/library/{book['id']}/entries",
        json={"type": "quote", "content": "x" * 10_001},
        headers=user_a["headers"],
    )
    assert response.status_code == 422


async def test_too_many_tags_are_rejected(client, user_a):
    book = await add_book(client, user_a["headers"])
    response = await client.post(
        f"/api/v1/library/{book['id']}/entries",
        json={"type": "quote", "content": "quote", "tags": [f"tag{i}" for i in range(16)]},
        headers=user_a["headers"],
    )
    assert response.status_code == 422


def test_tag_normalization_rules():
    assert normalize_tag("Деньги") == normalize_tag("деньги") == normalize_tag("  ДЕНЬГИ  ")
    assert normalize_tag("long   term") == "long term"


async def test_tags_are_deduplicated_case_insensitively(client, user_a):
    book = await add_book(client, user_a["headers"])
    await add_entry(
        client, user_a["headers"], book["id"], content="first", tags=["Деньги", "  деньги ", "ДЕНЬГИ"]
    )
    await add_entry(client, user_a["headers"], book["id"], content="second", tags=["деньги"])

    tags = await client.get("/api/v1/tags", headers=user_a["headers"])
    body = tags.json()
    assert len(body) == 1
    assert body[0]["name"] == "Деньги"  # first spelling wins as the display name
    assert body[0]["entries_count"] == 2


async def test_entries_can_be_filtered_by_tag(client, user_a):
    book = await add_book(client, user_a["headers"])
    await add_entry(client, user_a["headers"], book["id"], content="tagged", tags=["привычки"])
    await add_entry(client, user_a["headers"], book["id"], content="untagged")

    response = await client.get(
        f"/api/v1/library/{book['id']}/entries",
        params={"tag": "привычки"},
        headers=user_a["headers"],
    )
    assert [e["content"] for e in response.json()["items"]] == ["tagged"]


async def test_removing_all_tags_from_an_entry(client, user_a):
    book = await add_book(client, user_a["headers"])
    entry = await add_entry(client, user_a["headers"], book["id"], tags=["a", "b"])

    updated = await client.patch(
        f"/api/v1/entries/{entry['id']}", json={"tags": []}, headers=user_a["headers"]
    )
    assert updated.json()["tags"] == []
