from __future__ import annotations

import re

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.integrations.books.base import BookProvider, BookSearchResult

_ISBN_RE = re.compile(r"^(?:\d[\d\-\s]{8,}[\dXx])$")

# Google returns several sizes; pick the best available.
_COVER_PREFERENCE = ("extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail")


def looks_like_isbn(value: str) -> bool:
    stripped = value.replace("-", "").replace(" ", "")
    return stripped.isdigit() and len(stripped) in (10, 13) or bool(_ISBN_RE.match(value))


class GoogleBooksProvider(BookProvider):
    code = "google_books"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.GOOGLE_BOOKS_API_KEY
        self._base_url = (base_url or settings.GOOGLE_BOOKS_BASE_URL).rstrip("/")

    async def _request(self, params: dict) -> dict:
        if self._api_key:
            params["key"] = self._api_key
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/volumes", params=params)
                if response.status_code >= 400:
                    logger.warning("google_books_http_status=%s", response.status_code)
                    return {}
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("google_books_unavailable err=%s", type(exc).__name__)
            return {}

    async def search(self, query: str, *, limit: int = 20) -> list[BookSearchResult]:
        query = query.strip()
        if not query:
            return []
        q = f"isbn:{query.replace('-', '').replace(' ', '')}" if looks_like_isbn(query) else query
        data = await self._request({"q": q, "maxResults": min(limit, 40), "printType": "books"})
        items = data.get("items") or []
        results = [self._map(item) for item in items]
        return [r for r in results if r is not None][:limit]

    async def get_by_isbn(self, isbn: str) -> BookSearchResult | None:
        results = await self.search(isbn, limit=1)
        return results[0] if results else None

    def _map(self, item: dict) -> BookSearchResult | None:
        info = item.get("volumeInfo") or {}
        title = (info.get("title") or "").strip()
        if not title:
            return None

        isbn_10 = isbn_13 = None
        for ident in info.get("industryIdentifiers") or []:
            if ident.get("type") == "ISBN_13":
                isbn_13 = ident.get("identifier")
            elif ident.get("type") == "ISBN_10":
                isbn_10 = ident.get("identifier")

        published_year = None
        published = info.get("publishedDate") or ""
        if len(published) >= 4 and published[:4].isdigit():
            published_year = int(published[:4])

        images = info.get("imageLinks") or {}
        cover_url = next((images[k] for k in _COVER_PREFERENCE if images.get(k)), None)
        if cover_url:
            # Google serves http by default and adds a page-curl overlay.
            cover_url = cover_url.replace("http://", "https://").replace("&edge=curl", "")

        return BookSearchResult(
            source=self.code,
            source_id=item.get("id") or "",
            title=title,
            subtitle=info.get("subtitle"),
            authors=list(info.get("authors") or []),
            description=info.get("description"),
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            published_year=published_year,
            publisher=info.get("publisher"),
            cover_url=cover_url,
            categories=list(info.get("categories") or []),
        )
