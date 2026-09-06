from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.db.types import GUID, JSONBType


class Book(Base, UUIDMixin, TimestampMixin):
    """Global catalog entry. Shared by every user who adds the same book."""

    __tablename__ = "books"
    __table_args__ = (
        Index("ix_books_isbn_13", "isbn_13"),
        Index("ix_books_isbn_10", "isbn_10"),
        Index("ix_books_google_books_id", "google_books_id"),
        Index("ix_books_open_library_id", "open_library_id"),
        Index("ix_books_title", "title"),
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(512), nullable=True)
    authors: Mapped[list | None] = mapped_column(JSONBType(), nullable=True, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    isbn_10: Mapped[str | None] = mapped_column(String(16), nullable=True)
    isbn_13: Mapped[str | None] = mapped_column(String(20), nullable=True)
    published_year: Mapped[int | None] = mapped_column(nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    google_books_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    open_library_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONBType(), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def authors_list(self) -> list[str]:
        return list(self.authors or [])


class Category(Base, UUIDMixin):
    """User-specific. Two users can file the same book under different names."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_category_user_name"),
        Index("ix_categories_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )


class UserBook(Base, UUIDMixin, TimestampMixin):
    """A book in one user's library."""

    __tablename__ = "user_books"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_user_book"),
        Index("ix_user_books_user_id", "user_id"),
        Index("ix_user_books_book_id", "book_id"),
        Index("ix_user_books_created_at", "created_at"),
        Index("ix_user_books_user_favorite", "user_id", "is_favorite"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    book: Mapped[Book] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
