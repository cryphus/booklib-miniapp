from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import logger
from app.models import Book, Entry, EntryType, UserBook
from app.repositories import BookRepository, EntryRepository, TagRepository
from app.schemas.entry import EntryBookOut, EntryCreate, EntryOut, EntryUpdate, TagOut
from app.services.indexing_service import IndexingService


class EntryService:
    """CRUD for quotes and notes. Every read and write is scoped to the owning user."""

    def __init__(self, session: AsyncSession, indexing: IndexingService | None = None) -> None:
        self.session = session
        self.entries = EntryRepository(session)
        self.tags = TagRepository(session)
        self.books = BookRepository(session)
        self.indexing = indexing or IndexingService(session)

    async def _require_user_book(self, user_id: uuid.UUID, user_book_id: uuid.UUID) -> UserBook:
        user_book = await self.books.get_user_book(user_id, user_book_id)
        if user_book is None:
            raise NotFoundError("Book not found in your library", code="BOOK_NOT_FOUND")
        return user_book

    async def _require_entry(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> Entry:
        entry = await self.entries.get(user_id, entry_id)
        if entry is None:
            # Same 404 whether the row is missing or owned by somebody else.
            raise NotFoundError("Entry not found", code="ENTRY_NOT_FOUND")
        return entry

    async def create(
        self, user_id: uuid.UUID, user_book_id: uuid.UUID, payload: EntryCreate
    ) -> EntryOut:
        user_book = await self._require_user_book(user_id, user_book_id)
        entry = await self.entries.create(
            user_id=user_id,
            user_book_id=user_book.id,
            type=EntryType(payload.type),
            content=payload.content,
            personal_note=payload.personal_note if payload.type == "quote" else None,
            chapter=payload.chapter,
            page=payload.page,
            is_favorite=payload.is_favorite,
        )
        if payload.tags:
            await self.tags.set_entry_tags(entry, payload.tags)
        await self.session.flush()
        await self.indexing.index_entry(entry)
        return await self.to_dto(entry, user_book)

    async def update(
        self, user_id: uuid.UUID, entry_id: uuid.UUID, payload: EntryUpdate
    ) -> EntryOut:
        entry = await self._require_entry(user_id, entry_id)
        if payload.content is not None:
            entry.content = payload.content.strip()
        if payload.personal_note is not None:
            entry.personal_note = payload.personal_note or None
        if payload.chapter is not None:
            entry.chapter = payload.chapter or None
        if payload.page is not None:
            entry.page = payload.page or None
        if payload.is_favorite is not None:
            entry.is_favorite = payload.is_favorite
        if payload.tags is not None:
            await self.tags.set_entry_tags(entry, payload.tags)
        await self.session.flush()
        await self.indexing.index_entry(entry)
        return await self.to_dto(entry)

    async def set_favorite(
        self, user_id: uuid.UUID, entry_id: uuid.UUID, is_favorite: bool
    ) -> EntryOut:
        entry = await self._require_entry(user_id, entry_id)
        entry.is_favorite = is_favorite
        await self.session.flush()
        return await self.to_dto(entry)

    async def delete(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
        entry = await self._require_entry(user_id, entry_id)
        await self.indexing.remove_entry(entry.id)
        await self.entries.delete(entry)

    async def get(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> EntryOut:
        entry = await self._require_entry(user_id, entry_id)
        return await self.to_dto(entry)

    async def list_for_book(
        self,
        user_id: uuid.UUID,
        user_book_id: uuid.UUID,
        *,
        entry_type: str | None = None,
        favorite: bool | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EntryOut], int]:
        user_book = await self._require_user_book(user_id, user_book_id)
        entries, total = await self.entries.list_for_book(
            user_id,
            user_book.id,
            entry_type=EntryType(entry_type) if entry_type else None,
            favorite=favorite,
            tag=tag,
            limit=limit,
            offset=offset,
        )
        return [await self.to_dto(e, user_book) for e in entries], total

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        entry_type: str | None = None,
        favorite: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EntryOut], int]:
        entries, total = await self.entries.list_for_user(
            user_id,
            entry_type=EntryType(entry_type) if entry_type else None,
            favorite=favorite,
            limit=limit,
            offset=offset,
        )
        books = await self.entries.books_for_entries(entries)
        return [
            self._dto(entry, *(books.get(entry.user_book_id) or (None, None))) for entry in entries
        ], total

    async def to_dto(self, entry: Entry, user_book: UserBook | None = None) -> EntryOut:
        if user_book is None:
            mapping = await self.entries.books_for_entries([entry])
            pair = mapping.get(entry.user_book_id)
            return self._dto(entry, *(pair or (None, None)))
        return self._dto(entry, user_book, user_book.book)

    @staticmethod
    def _dto(entry: Entry, user_book: UserBook | None, book: Book | None) -> EntryOut:
        book_dto = None
        if user_book is not None and book is not None:
            book_dto = EntryBookOut(
                user_book_id=user_book.id,
                book_id=book.id,
                title=book.title,
                authors=list(book.authors or []),
                cover_url=book.cover_url,
            )
        elif user_book is not None:
            logger.debug("entry_without_book entry_id=%s", entry.id)
        return EntryOut(
            id=entry.id,
            user_book_id=entry.user_book_id,
            type=entry.type.value if hasattr(entry.type, "value") else str(entry.type),
            content=entry.content,
            personal_note=entry.personal_note,
            chapter=entry.chapter,
            page=entry.page,
            is_favorite=entry.is_favorite,
            tags=[TagOut(id=t.id, name=t.name) for t in entry.tags],
            book=book_dto,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
