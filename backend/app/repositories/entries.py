from __future__ import annotations

import uuid

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Book, Entry, EntryTag, EntryType, Tag, UserBook


class EntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> Entry | None:
        """Ownership is part of the query, never a post-hoc check."""
        stmt = (
            select(Entry)
            .where(Entry.id == entry_id, Entry.user_id == user_id)
            .options(selectinload(Entry.tags))
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_many(self, user_id: uuid.UUID, entry_ids: list[uuid.UUID]) -> list[Entry]:
        if not entry_ids:
            return []
        stmt = (
            select(Entry)
            .where(Entry.id.in_(entry_ids), Entry.user_id == user_id)
            .options(selectinload(Entry.tags))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    def _base_query(self, user_id: uuid.UUID) -> Select:
        return select(Entry).where(Entry.user_id == user_id).options(selectinload(Entry.tags))

    async def list_for_book(
        self,
        user_id: uuid.UUID,
        user_book_id: uuid.UUID,
        *,
        entry_type: EntryType | None = None,
        favorite: bool | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Entry], int]:
        stmt = self._base_query(user_id).where(Entry.user_book_id == user_book_id)
        if entry_type is not None:
            stmt = stmt.where(Entry.type == entry_type)
        if favorite is not None:
            stmt = stmt.where(Entry.is_favorite.is_(favorite))
        if tag:
            stmt = stmt.join(EntryTag, EntryTag.entry_id == Entry.id).join(
                Tag, Tag.id == EntryTag.tag_id
            ).where(Tag.user_id == user_id, Tag.normalized_name == tag.strip().lower())

        total = (
            await self.session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        stmt = stmt.order_by(Entry.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).unique().scalars().all()), total

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        entry_type: EntryType | None = None,
        favorite: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Entry], int]:
        stmt = self._base_query(user_id)
        if entry_type is not None:
            stmt = stmt.where(Entry.type == entry_type)
        if favorite is not None:
            stmt = stmt.where(Entry.is_favorite.is_(favorite))
        total = (
            await self.session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        stmt = stmt.order_by(Entry.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).unique().scalars().all()), total

    async def create(self, **fields) -> Entry:
        entry = Entry(**fields)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def delete(self, entry: Entry) -> None:
        await self.session.delete(entry)
        await self.session.flush()

    async def search(
        self, user_id: uuid.UUID, query: str, *, limit: int = 20
    ) -> list[Entry]:
        pattern = f"%{query.strip()}%"
        stmt = (
            self._base_query(user_id)
            .where(
                or_(
                    Entry.content.ilike(pattern),
                    func.coalesce(Entry.personal_note, "").ilike(pattern),
                    func.coalesce(Entry.chapter, "").ilike(pattern),
                )
            )
            .order_by(Entry.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).unique().scalars().all())

    async def search_by_tag(self, user_id: uuid.UUID, query: str, *, limit: int = 20) -> list[Entry]:
        pattern = f"%{query.strip().lower()}%"
        stmt = (
            self._base_query(user_id)
            .join(EntryTag, EntryTag.entry_id == Entry.id)
            .join(Tag, Tag.id == EntryTag.tag_id)
            .where(Tag.user_id == user_id, Tag.normalized_name.like(pattern))
            .order_by(Entry.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).unique().scalars().all())

    async def books_for_entries(
        self, entries: list[Entry]
    ) -> dict[uuid.UUID, tuple[UserBook, Book]]:
        ids = [e.user_book_id for e in entries]
        if not ids:
            return {}
        stmt = (
            select(UserBook, Book)
            .join(Book, Book.id == UserBook.book_id)
            .where(UserBook.id.in_(ids))
        )
        return {ub.id: (ub, book) for ub, book in (await self.session.execute(stmt)).all()}

    async def counts_by_type(self, user_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(Entry.type, func.count())
            .where(Entry.user_id == user_id)
            .group_by(Entry.type)
        )
        rows = (await self.session.execute(stmt)).all()
        counts = {"quote": 0, "note": 0}
        for entry_type, count in rows:
            key = entry_type.value if hasattr(entry_type, "value") else str(entry_type)
            counts[key] = count
        return counts

    async def clear_tags(self, entry_id: uuid.UUID) -> None:
        await self.session.execute(delete(EntryTag).where(EntryTag.entry_id == entry_id))
