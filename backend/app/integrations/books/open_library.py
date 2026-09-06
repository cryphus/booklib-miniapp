from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.integrations.books.base import BookProvider, BookSearchResult
from app.integrations.books.google_books import looks_like_isbn

COVERS_BASE = "https://covers.openlibrary.org/b"

# Only the fields we actually map. `fields=*` returns megabytes per query and regularly
# times out.
SEARCH_FIELDS = ",".join(
    [
        "key",
        "title",
        "author_name",
        "isbn",
        "cover_i",
        "first_publish_year",
        "publisher",
        "subject",
        "first_sentence",
    ]
)


class OpenLibraryProvider(BookProvider):
    """Fallback catalog. Never the only source, per the product spec."""

    code = "open_library"

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.OPEN_LIBRARY_BASE_URL).rstrip("/")

    async def _request(self, path: str, params: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                if response.status_code >= 400:
                    logger.warning("open_library_http_status=%s", response.status_code)
                    return {}
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("open_library_unavailable err=%s", type(exc).__name__)
            return {}

    async def search(self, query: str, *, limit: int = 20) -> list[BookSearchResult]:
        query = query.strip()
        if not query:
            return []
        params: dict = {"limit": min(limit, 40), "fields": SEARCH_FIELDS}
        if looks_like_isbn(query):
            params["isbn"] = query.replace("-", "").replace(" ", "")
        else:
            params["q"] = query
        data = await self._request("/search.json", params)
        docs = data.get("docs") or []
        results = [self._map(doc) for doc in docs]
        return [r for r in results if r is not None][:limit]

    async def get_by_isbn(self, isbn: str) -> BookSearchResult | None:
        results = await self.search(isbn, limit=1)
        return results[0] if results else None

    def _map(self, doc: dict) -> BookSearchResult | None:
        title = (doc.get("title") or "").strip()
        if not title:
            return None

        isbns = doc.get("isbn") or []
        isbn_13 = next((i for i in isbns if len(i) == 13), None)
        isbn_10 = next((i for i in isbns if len(i) == 10), None)

        cover_url = None
        if doc.get("cover_i"):
            cover_url = f"{COVERS_BASE}/id/{doc['cover_i']}-L.jpg"
        elif isbn_13 or isbn_10:
            cover_url = f"{COVERS_BASE}/isbn/{isbn_13 or isbn_10}-L.jpg"

        description = doc.get("first_sentence")
        if isinstance(description, list):
            description = description[0] if description else None
        elif isinstance(description, dict):
            description = description.get("value")

        publishers = doc.get("publisher") or []
        key = (doc.get("key") or "").replace("/works/", "")

        return BookSearchResult(
            source=self.code,
            source_id=key,
            title=title,
            authors=list(doc.get("author_name") or []),
            description=description,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            published_year=doc.get("first_publish_year"),
            publisher=publishers[0] if publishers else None,
            cover_url=cover_url,
            categories=list((doc.get("subject") or [])[:5]),
        )

    @staticmethod
    def cover_url_for_isbn(isbn: str, size: str = "L") -> str:
        return f"{COVERS_BASE}/isbn/{isbn}-{size}.jpg"
