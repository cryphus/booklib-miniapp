from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin, utcnow
from app.db.types import GUID


class AIContextType(str, enum.Enum):
    all_library = "all_library"
    current_book = "current_book"
    favorites = "favorites"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class AIConversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        Index("ix_ai_conversations_user_id", "user_id"),
        Index("ix_ai_conversations_updated_at", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New chat")
    context_type: Mapped[AIContextType] = mapped_column(
        Enum(AIContextType, name="ai_context_type", native_enum=False, length=32),
        default=AIContextType.all_library,
        nullable=False,
    )
    context_user_book_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("user_books.id", ondelete="SET NULL"), nullable=True
    )

    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="AIMessage.created_at"
    )


class AIMessage(Base, UUIDMixin):
    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_conversation_id", "conversation_id"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="ai_message_role", native_enum=False, length=16), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )

    conversation: Mapped[AIConversation] = relationship(back_populates="messages")
    sources: Mapped[list["AIMessageSource"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", lazy="selectin"
    )


class AIMessageSource(Base, UUIDMixin):
    __tablename__ = "ai_message_sources"
    __table_args__ = (Index("ix_ai_message_sources_message_id", "message_id"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("ai_messages.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    message: Mapped[AIMessage] = relationship(back_populates="sources")


class AIUsage(Base, UUIDMixin):
    """One row per user per billing period. Quota is enforced only here, server-side."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "period_start", name="uq_ai_usage_user_period"),
        Index("ix_ai_usage_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[int] = mapped_column(default=0, nullable=False)
