from __future__ import annotations

from app.integrations.books.aggregator import BookSearchAggregator
from app.integrations.books.base import BookProvider, BookSearchResult
from app.repositories import BookRepository
from tests.conftest import add_book


class StubProvider(BookProvider):
    def __init__(self, code: str, results: list[BookSearchResult]) -> None:
        self.code = code
        self._results = results
        self.calls = 0

    async def search(self, query: str, *, limit: int = 20) -> list[BookSearchResult]:
        self.calls += 1
        return list(self._results)

    async def get_by_isbn(self, isbn: str) -> BookSearchResult | None:
        return self._results[0] if self._results else None


def _result(source: str, title: str, isbn_13: str | None = None) -> BookSearchResult:
    return BookSearchResult(
        source=source, source_id=f"{source}-{title}", title=title, isbn_13=isbn_13
    )


async def test_open_library_is_used_only_as_fallback():
    google = StubProvider("google_books", [_result("google_books", f"Book {i}") for i in range(10)])
    open_library = StubProvider("open_library", [_result("open_library", "Fallback")])
    aggregator = BookSearchAggregator(google, open_library, min_results=5)

    results = await aggregator.search("habits")

    assert open_library.calls == 0
    assert all(r.source == "google_books" for r in results)


async def test_thin_google_results_are_topped_up_from_open_library():
    google = StubProvider("google_books", [_result("google_books", "Only one")])
    open_library = StubProvider("open_library", [_result("open_library", "Extra")])
    aggregator = BookSearchAggregator(google, open_library, min_results=5)

    results = await aggregator.search("rare book")

    assert open_library.calls == 1
    assert {r.source for r in results} == {"google_books", "open_library"}


async def test_merge_drops_duplicates_across_providers():
    shared_isbn = "9781234567890"
    google = StubProvider("google_books", [_result("google_books", "Same", shared_isbn)])
    open_library = StubProvider("open_library", [_result("open_library", "Same", shared_isbn)])
    aggregator = BookSearchAggregator(google, open_library, min_results=5)

    results = await aggregator.search("same")

    assert len(results) == 1
    assert results[0].source == "google_books"


async def test_catalog_book_is_shared_between_users(client, user_a, user_b, session):
    payload = {
        "source": "google_books",
        "source_id": "gb-atomic-habits",
        "title": "Atomic Habits",
        "authors": ["James Clear"],
        "isbn_13": "9780735211292",
    }
    first = await client.post("/api/v1/books", json=payload, headers=user_a["headers"])
    second = await client.post("/api/v1/books", json=payload, headers=user_b["headers"])

    assert first.status_code == 201
    assert second.status_code == 201
    # One catalog row, two library rows.
    assert first.json()["book"]["id"] == second.json()["book"]["id"]
    assert first.json()["id"] != second.json()["id"]


async def test_dedup_matches_on_isbn13_before_provider_id(client, user_a):
    await client.post(
        "/api/v1/books",
        json={
            "source": "google_books",
            "source_id": "gb-1",
            "title": "Psychology of Money",
            "isbn_13": "9780857197689",
        },
        headers=user_a["headers"],
    )
    # A second user adds the same ISBN found through a different provider.
    response = await client.post(
        "/api/v1/books",
        json={
            "source": "open_library",
            "source_id": "OL123W",
            "title": "Psychology of Money (reprint)",
            "isbn_13": "9780857197689",
        },
        headers=user_a["headers"],
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BOOK_ALREADY_ADDED"


async def test_repository_dedup_priority(session, engine):
    repo = BookRepository(session)
    book = await repo.create_book(
        title="Dedup Target",
        isbn_13="9781111111111",
        isbn_10="1111111111",
        google_books_id="gb-x",
        open_library_id="OL9W",
        source="google_books",
    )
    await session.flush()

    assert (await repo.find_duplicate(isbn_13="9781111111111")).id == book.id
    assert (await repo.find_duplicate(isbn_10="1111111111")).id == book.id
    assert (await repo.find_duplicate(google_books_id="gb-x")).id == book.id
    assert (await repo.find_duplicate(open_library_id="OL9W")).id == book.id
    assert await repo.find_duplicate(isbn_13="9789999999999") is None


async def test_manual_book_requires_title(client, user_a):
    response = await client.post("/api/v1/books/manual", json={"title": ""}, headers=user_a["headers"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_library_filters_and_categories(client, user_a):
    business = await add_book(client, user_a["headers"], "Business Book", category="Бизнес")
    await add_book(client, user_a["headers"], "Fiction Book", category="Художественная")

    await client.patch(
        f"/api/v1/library/{business['id']}", json={"is_favorite": True}, headers=user_a["headers"]
    )

    by_category = await client.get(
        "/api/v1/library", params={"category": "бизнес"}, headers=user_a["headers"]
    )
    assert [i["book"]["title"] for i in by_category.json()["items"]] == ["Business Book"]

    favorites = await client.get(
        "/api/v1/library", params={"favorite": True}, headers=user_a["headers"]
    )
    assert [i["book"]["title"] for i in favorites.json()["items"]] == ["Business Book"]

    categories = await client.get("/api/v1/library/categories", headers=user_a["headers"])
    assert {c["name"] for c in categories.json()} == {"Бизнес", "Художественная"}


async def test_categories_are_user_specific(client, user_a, user_b):
    payload = {
        "source": "google_books",
        "source_id": "gb-shared",
        "title": "Shared Book",
        "isbn_13": "9780000000001",
        "category": "Бизнес",
    }
    await client.post("/api/v1/books", json=payload, headers=user_a["headers"])
    await client.post(
        "/api/v1/books",
        json={**payload, "category": "Саморазвитие"},
        headers=user_b["headers"],
    )

    a_library = await client.get("/api/v1/library", headers=user_a["headers"])
    b_library = await client.get("/api/v1/library", headers=user_b["headers"])

    assert a_library.json()["items"][0]["category"]["name"] == "Бизнес"
    assert b_library.json()["items"][0]["category"]["name"] == "Саморазвитие"
    # Same underlying catalog book.
    assert a_library.json()["items"][0]["book"]["id"] == b_library.json()["items"][0]["book"]["id"]


async def test_removing_a_book_keeps_the_shared_catalog_row(client, user_a, user_b):
    payload = {
        "source": "google_books",
        "source_id": "gb-keep",
        "title": "Kept Book",
        "isbn_13": "9780000000002",
    }
    a_book = await client.post("/api/v1/books", json=payload, headers=user_a["headers"])
    await client.post("/api/v1/books", json=payload, headers=user_b["headers"])

    await client.delete(f"/api/v1/library/{a_book.json()['id']}", headers=user_a["headers"])

    b_library = await client.get("/api/v1/library", headers=user_b["headers"])
    assert b_library.json()["total"] == 1
    assert b_library.json()["items"][0]["book"]["title"] == "Kept Book"
