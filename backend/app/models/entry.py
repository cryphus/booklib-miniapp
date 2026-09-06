from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.db.types import GUID, EmbeddingVector


class EntryType(str, enum.Enum):
    quote = "quote"
    note = "note"


class Entry(Base, UUIDMixin, TimestampMixin):
    """One entity for both quotes and personal notes."""

    __tablename__ = "entries"
    __table_args__ = (
        Index("ix_entries_user_id", "user_id"),
        Index("ix_entries_user_book_id", "user_book_id"),
        Index("ix_entries_created_at", "created_at"),
        Index("ix_entries_user_type", "user_id", "type"),
        Index("ix_entries_user_favorite", "user_id", "is_favorite"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_book_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user_books.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, name="entry_type", native_enum=False, length=16), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    personal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tags: Mapped[list["Tag"]] = relationship(
        secondary="entry_tags", lazy="selectin", back_populates="entries"
    )
    embedding: Mapped["EntryEmbedding | None"] = relationship(
        back_populates="entry", cascade="all, delete-orphan", uselist=False
    )


class Tag(Base, UUIDMixin):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_tag_user_normalized"),
        Index("ix_tags_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )

    entries: Mapped[list[Entry]] = relationship(secondary="entry_tags", back_populates="tags")


class EntryTag(Base):
    __tablename__ = "entry_tags"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class EntryEmbedding(Base, UUIDMixin):
    """RAG index row. Always filtered by user_id server-side."""

    __tablename__ = "entry_embeddings"
    __table_args__ = (
        UniqueConstraint("entry_id", name="uq_entry_embedding_entry"),
        Index("ix_entry_embeddings_user_id", "user_id"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    document: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    entry: Mapped[Entry] = relationship(back_populates="embedding")
