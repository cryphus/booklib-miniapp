from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntryType
from app.repositories import BookRepository, EntryRepository
from app.schemas.entry import EntryOut
from app.schemas.search import SearchResults
from app.services.entry_service import EntryService
from app.services.library_service import LibraryService


class SearchService:
    """Global search across the user's own books, quotes, notes and tags.

    PostgreSQL ILIKE/trigram is enough for the MVP volume; the trigram indexes created by
    the migration keep it fast, and it handles Russian text without extra configuration.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.books = BookRepository(session)
        self.entries = EntryRepository(session)
        self.entry_service = EntryService(session)

    async def search(self, user_id: uuid.UUID, query: str, *, limit: int = 20) -> SearchResults:
        query = query.strip()
        if not query:
            return SearchResults(query=query)

        books, _total = await self.books.list_library(user_id, search=query, limit=limit)
        counts = await self.books.entry_counts([b.id for b in books])
        book_dtos = [LibraryService.to_dto(b, counts.get(b.id)) for b in books]

        matched = await self.entries.search(user_id, query, limit=limit * 2)
        by_tag = await self.entries.search_by_tag(user_id, query, limit=limit)
        seen = {e.id for e in matched}
        matched.extend(e for e in by_tag if e.id not in seen)

        book_map = await self.entries.books_for_entries(matched)
        quotes: list[EntryOut] = []
        notes: list[EntryOut] = []
        for entry in matched:
            pair = book_map.get(entry.user_book_id)
            dto = EntryService._dto(entry, *(pair or (None, None)))
            if entry.type == EntryType.quote:
                quotes.append(dto)
            else:
                notes.append(dto)

        quotes = quotes[:limit]
        notes = notes[:limit]
        return SearchResults(
            query=query,
            books=book_dtos,
            quotes=quotes,
            notes=notes,
            total=len(book_dtos) + len(quotes) + len(notes),
        )
