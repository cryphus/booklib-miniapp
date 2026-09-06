from __future__ import annotations

from tests.conftest import add_book, add_entry


async def test_search_groups_results_by_kind(client, user_a):
    book = await add_book(
        client, user_a["headers"], "Психология денег", authors=["Морган Хаузел"]
    )
    quote = await add_entry(
        client,
        user_a["headers"],
        book["id"],
        type="quote",
        content="Богатство — это то, чего вы не видите.",
    )
    note = await add_entry(
        client,
        user_a["headers"],
        book["id"],
        type="note",
        content="Мысль про богатство и сбережения.",
    )

    response = await client.get(
        "/api/v1/search", params={"q": "богатство"}, headers=user_a["headers"]
    )
    body = response.json()
    assert [q["id"] for q in body["quotes"]] == [quote["id"]]
    assert [n["id"] for n in body["notes"]] == [note["id"]]
    assert body["total"] == 2


async def test_search_matches_russian_book_titles_and_authors(client, user_a):
    await add_book(client, user_a["headers"], "Психология денег", authors=["Морган Хаузел"])
    await add_book(client, user_a["headers"], "Атомные привычки", authors=["Джеймс Клир"])

    by_title = await client.get(
        "/api/v1/search", params={"q": "привычки"}, headers=user_a["headers"]
    )
    assert [b["book"]["title"] for b in by_title.json()["books"]] == ["Атомные привычки"]

    by_author = await client.get(
        "/api/v1/search", params={"q": "хаузел"}, headers=user_a["headers"]
    )
    assert [b["book"]["title"] for b in by_author.json()["books"]] == ["Психология денег"]


async def test_search_is_case_insensitive(client, user_a):
    book = await add_book(client, user_a["headers"], "Test")
    await add_entry(client, user_a["headers"], book["id"], content="ДОЛГОСРОЧНОЕ мышление")

    response = await client.get(
        "/api/v1/search", params={"q": "долгосрочное"}, headers=user_a["headers"]
    )
    assert len(response.json()["quotes"]) == 1


async def test_search_finds_entries_by_tag(client, user_a):
    book = await add_book(client, user_a["headers"], "Tagged Book")
    entry = await add_entry(
        client, user_a["headers"], book["id"], content="Ничего общего", tags=["инвестиции"]
    )

    response = await client.get(
        "/api/v1/search", params={"q": "инвестиции"}, headers=user_a["headers"]
    )
    assert [q["id"] for q in response.json()["quotes"]] == [entry["id"]]


async def test_search_result_carries_book_link_for_navigation(client, user_a):
    book = await add_book(client, user_a["headers"], "Navigable")
    entry = await add_entry(client, user_a["headers"], book["id"], content="уникальный текст")

    response = await client.get(
        "/api/v1/search", params={"q": "уникальный"}, headers=user_a["headers"]
    )
    found = response.json()["quotes"][0]
    # The frontend opens /book/<user_book_id>?entry=<entry_id> from these two fields.
    assert found["id"] == entry["id"]
    assert found["user_book_id"] == book["id"]
    assert found["book"]["title"] == "Navigable"


async def test_empty_search_returns_empty_groups(client, user_a):
    response = await client.get(
        "/api/v1/search", params={"q": "несуществующее"}, headers=user_a["headers"]
    )
    body = response.json()
    assert body["books"] == [] and body["quotes"] == [] and body["notes"] == []
    assert body["total"] == 0


async def test_search_query_is_required(client, user_a):
    response = await client.get("/api/v1/search", params={"q": ""}, headers=user_a["headers"])
    assert response.status_code == 422


async def test_pagination_page_size_is_capped(client, user_a):
    response = await client.get(
        "/api/v1/library", params={"page_size": 500}, headers=user_a["headers"]
    )
    assert response.status_code == 422
