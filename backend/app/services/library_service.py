from __future__ import annotations

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import logger
from app.integrations.books import BookSearchAggregator, BookSearchResult, get_book_search
from app.models import Book, UserBook
from app.repositories import BookRepository
from app.schemas.book import AddBookFromCatalog, BookOut, CategoryOut, ManualBookCreate, UserBookOut
from app.services.storage import StorageService, get_storage, sniff_image_mime

MAX_COVER_BYTES = 4 * 1024 * 1024


class LibraryService:
    def __init__(
        self,
        session: AsyncSession,
        search: BookSearchAggregator | None = None,
        storage: StorageService | None = None,
    ) -> None:
        self.session = session
        self.books = BookRepository(session)
        self.search_provider = search or get_book_search()
        self.storage = storage or get_storage()

    # ---------- catalog search ----------

    async def search_catalog(self, query: str, limit: int = 20) -> list[BookSearchResult]:
        return await self.search_provider.search(query, limit=limit)

    # ---------- adding books ----------

    async def add_from_catalog(self, user_id: uuid.UUID, payload: AddBookFromCatalog) -> UserBook:
        book = await self.books.find_duplicate(
            isbn_13=payload.isbn_13,
            isbn_10=payload.isbn_10,
            google_books_id=payload.source_id if payload.source == "google_books" else None,
            open_library_id=payload.source_id if payload.source == "open_library" else None,
        )
        if book is None:
            cover_url = await self._store_cover(payload.cover_url)
            book = await self.books.create_book(
                title=payload.title[:512],
                subtitle=payload.subtitle,
                authors=payload.authors,
                description=payload.description,
                isbn_10=payload.isbn_10,
                isbn_13=payload.isbn_13,
                published_year=payload.published_year,
                publisher=payload.publisher,
                cover_url=cover_url,
                google_books_id=payload.source_id if payload.source == "google_books" else None,
                open_library_id=payload.source_id if payload.source == "open_library" else None,
                source=payload.source,
                meta={"original_cover_url": payload.cover_url} if payload.cover_url else None,
                created_by_user_id=user_id,
            )
        return await self._attach_to_library(user_id, book, payload.category)

    async def add_manual(self, user_id: uuid.UUID, payload: ManualBookCreate) -> UserBook:
        book = await self.books.create_book(
            title=payload.title[:512],
            authors=payload.authors,
            description=payload.description,
            cover_url=payload.cover_url,
            published_year=payload.published_year,
            source="manual",
            created_by_user_id=user_id,
        )
        return await self._attach_to_library(user_id, book, payload.category)

    async def _attach_to_library(
        self, user_id: uuid.UUID, book: Book, category_name: str | None
    ) -> UserBook:
        existing = await self.books.get_user_book_by_book(user_id, book.id)
        if existing is not None:
            raise ConflictError("This book is already in your library", code="BOOK_ALREADY_ADDED")
        category = (
            await self.books.get_or_create_category(user_id, category_name)
            if category_name
            else None
        )
        return await self.books.add_to_library(user_id, book.id, category.id if category else None)

    async def _store_cover(self, external_url: str | None) -> str | None:
        """Mirror the provider cover into our own storage; fall back to the source URL."""
        if not external_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(external_url)
            if response.status_code >= 400 or len(response.content) > MAX_COVER_BYTES:
                return external_url
            mime = sniff_image_mime(response.content)
            if mime is None:
                return external_url
            stored = await self.storage.save(response.content, content_type=mime, prefix="covers")
            return stored.url
        except (httpx.HTTPError, OSError, ValidationError) as exc:
            logger.info("cover_mirror_failed err=%s", type(exc).__name__)
            return external_url

    # ---------- reading the library ----------

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
    ) -> tuple[list[UserBookOut], int]:
        items, total = await self.books.list_library(
            user_id,
            category=category,
            favorite=favorite,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        counts = await self.books.entry_counts([i.id for i in items])
        return [self.to_dto(i, counts.get(i.id)) for i in items], total

    async def get_user_book(self, user_id: uuid.UUID, user_book_id: uuid.UUID) -> UserBookOut:
        user_book = await self.books.get_user_book(user_id, user_book_id)
        if user_book is None:
            raise NotFoundError("Book not found in your library", code="BOOK_NOT_FOUND")
        counts = await self.books.entry_counts([user_book.id])
        return self.to_dto(user_book, counts.get(user_book.id))

    async def update_user_book(
        self,
        user_id: uuid.UUID,
        user_book_id: uuid.UUID,
        *,
        category: str | None = None,
        is_favorite: bool | None = None,
    ) -> UserBookOut:
        user_book = await self.books.get_user_book(user_id, user_book_id)
        if user_book is None:
            raise NotFoundError("Book not found in your library", code="BOOK_NOT_FOUND")
        if is_favorite is not None:
            user_book.is_favorite = is_favorite
        if category is not None:
            if category.strip():
                cat = await self.books.get_or_create_category(user_id, category)
                user_book.category_id = cat.id if cat else None
            else:
                user_book.category_id = None
        await self.session.flush()
        await self.session.refresh(user_book)
        counts = await self.books.entry_counts([user_book.id])
        return self.to_dto(user_book, counts.get(user_book.id))

    async def remove_user_book(self, user_id: uuid.UUID, user_book_id: uuid.UUID) -> None:
        """Removes the book from this library only; the shared catalog row survives."""
        user_book = await self.books.get_user_book(user_id, user_book_id)
        if user_book is None:
            raise NotFoundError("Book not found in your library", code="BOOK_NOT_FOUND")
        await self.books.delete_user_book(user_book)

    async def list_categories(self, user_id: uuid.UUID) -> list[CategoryOut]:
        return [CategoryOut.model_validate(c) for c in await self.books.list_categories(user_id)]

    @staticmethod
    def to_dto(user_book: UserBook, counts: dict[str, int] | None = None) -> UserBookOut:
        counts = counts or {"quotes": 0, "notes": 0, "total": 0}
        return UserBookOut(
            id=user_book.id,
            book=BookOut.model_validate(user_book.book),
            category=CategoryOut.model_validate(user_book.category) if user_book.category else None,
            is_favorite=user_book.is_favorite,
            entries_count=counts.get("total", 0),
            quotes_count=counts.get("quotes", 0),
            notes_count=counts.get("notes", 0),
            created_at=user_book.created_at,
            updated_at=user_book.updated_at,
        )
