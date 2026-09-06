from __future__ import annotations

from app.core.config import settings
from app.integrations.books.base import BookProvider, BookSearchResult
from app.integrations.books.google_books import GoogleBooksProvider
from app.integrations.books.open_library import OpenLibraryProvider


class BookSearchAggregator:
    """Google Books first; Open Library only tops up a thin result set."""

    def __init__(
        self,
        primary: BookProvider | None = None,
        fallback: BookProvider | None = None,
        *,
        min_results: int | None = None,
    ) -> None:
        self.primary = primary or GoogleBooksProvider()
        self.fallback = fallback or OpenLibraryProvider()
        self.min_results = (
            min_results if min_results is not None else settings.BOOK_SEARCH_MIN_RESULTS
        )

    async def search(self, query: str, *, limit: int = 20) -> list[BookSearchResult]:
        results = await self.primary.search(query, limit=limit)
        if len(results) < max(self.min_results, 1):
            extra = await self.fallback.search(query, limit=limit)
            results = self._merge(results, extra)
        return results[:limit]

    @staticmethod
    def _merge(
        primary: list[BookSearchResult], secondary: list[BookSearchResult]
    ) -> list[BookSearchResult]:
        seen = {r.dedup_key for r in primary}
        merged = list(primary)
        for candidate in secondary:
            if candidate.dedup_key in seen:
                continue
            seen.add(candidate.dedup_key)
            merged.append(candidate)
        return merged


def get_book_search() -> BookSearchAggregator:
    return BookSearchAggregator()
