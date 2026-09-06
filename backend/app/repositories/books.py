from __future__ import annotations

import uuid

from sqlalchemy import Select, Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, Category, Entry, EntryType, UserBook


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


class BookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- global catalog ----------

    async def get_book(self, book_id: uuid.UUID) -> Book | None:
        return await self.session.get(Book, book_id)

    async def find_duplicate(
        self,
        *,
        isbn_13: str | None = None,
        isbn_10: str | None = None,
        google_books_id: str | None = None,
        open_library_id: str | None = None,
    ) -> Book | None:
        """Checked in priority order: ISBN-13, ISBN-10, then the provider ids."""
        for column, value in (
            (Book.isbn_13, isbn_13),
            (Book.isbn_10, isbn_10),
            (Book.google_books_id, google_books_id),
            (Book.open_library_id, open_library_id),
        ):
            if not value:
                continue
            stmt = select(Book).where(column == value).limit(1)
            found = (await self.session.execute(stmt)).scalars().first()
            if found:
                return found
        return None

    async def create_book(self, **fields) -> Book:
        book = Book(**fields)
        self.session.add(book)
        await self.session.flush()
        return book

    # ---------- categories (user-scoped) ----------

    async def get_or_create_category(self, user_id: uuid.UUID, name: str) -> Category | None:
        name = name.strip()
        if not name:
            return None
        normalized = normalize_name(name)
        stmt = select(Category).where(
            Category.user_id == user_id, Category.normalized_name == normalized
        )
        category = (await self.session.execute(stmt)).scalars().first()
        if category:
            return category
        category = Category(user_id=user_id, name=name, normalized_name=normalized)
        self.session.add(category)
        await self.session.flush()
        return category

    async def list_categories(self, user_id: uuid.UUID) -> list[Category]:
        stmt = select(Category).where(Category.user_id == user_id).order_by(Category.name)
        return list((await self.session.execute(stmt)).scalars().all())

    # ---------- user library ----------

    async def get_user_book(self, user_id: uuid.UUID, user_book_id: uuid.UUID) -> UserBook | None:
        """Always filtered by user_id: a foreign UUID can never resolve."""
        stmt = select(UserBook).where(UserBook.id == user_book_id, UserBook.user_id == user_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def get_user_book_by_book(self, user_id: uuid.UUID, book_id: uuid.UUID) -> UserBook | None:
        stmt = select(UserBook).where(UserBook.user_id == user_id, UserBook.book_id == book_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def add_to_library(
        self,
        user_id: uuid.UUID,
        book_id: uuid.UUID,
        category_id: uuid.UUID | None = None,
    ) -> UserBook:
        user_book = UserBook(user_id=user_id, book_id=book_id, category_id=category_id)
        self.session.add(user_book)
        await self.session.flush()
        await self.session.refresh(user_book)
        return user_book

    def _library_query(
        self,
        user_id: uuid.UUID,
        *,
        category: str | None = None,
        favorite: bool | None = None,
        search: str | None = None,
    ) -> Select:
        stmt = select(UserBook).join(Book, Book.id == UserBook.book_id).where(
            UserBook.user_id == user_id
        )
        if favorite is not None:
            stmt = stmt.where(UserBook.is_favorite.is_(favorite))
        if category:
            stmt = stmt.join(Category, Category.id == UserBook.category_id).where(
                Category.normalized_name == normalize_name(category)
            )
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Book.title.ilike(pattern),
                    func.coalesce(Book.subtitle, "").ilike(pattern),
                    cast(Book.authors, Text).ilike(pattern),
                )
            )
        return stmt

    async def list_library(
        self,
        user_id: uuid.UUID,
        *,
        category: str | None = None,
        favorite: bool | None = None,
        search: str | None = None,
        sort: str = "recent",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[UserBook], int]:
        stmt = self._library_query(
            user_id, category=category, favorite=favorite, search=search
        )
        total = (
            await self.session.execute(
                select(func.count()).select_from(stmt.subquery())
            )
        ).scalar_one()

        order = {
            "recent": UserBook.created_at.desc(),
            "oldest": UserBook.created_at.asc(),
            "title": Book.title.asc(),
        }.get(sort, UserBook.created_at.desc())

        stmt = stmt.order_by(order).limit(limit).offset(offset)
        items = list((await self.session.execute(stmt)).unique().scalars().all())
        return items, total

    async def entry_counts(self, user_book_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        if not user_book_ids:
            return {}
        stmt = (
            select(Entry.user_book_id, Entry.type, func.count())
            .where(Entry.user_book_id.in_(user_book_ids))
            .group_by(Entry.user_book_id, Entry.type)
        )
        counts: dict[uuid.UUID, dict[str, int]] = {}
        for user_book_id, entry_type, count in (await self.session.execute(stmt)).all():
            bucket = counts.setdefault(user_book_id, {"quotes": 0, "notes": 0, "total": 0})
            key = "quotes" if entry_type == EntryType.quote else "notes"
            bucket[key] += count
            bucket["total"] += count
        return counts

    async def delete_user_book(self, user_book: UserBook) -> None:
        await self.session.delete(user_book)
        await self.session.flush()

    async def book_used_by_others(self, book_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = select(func.count()).select_from(UserBook).where(
            UserBook.book_id == book_id, UserBook.user_id != user_id
        )
        return bool((await self.session.execute(stmt)).scalar_one())
