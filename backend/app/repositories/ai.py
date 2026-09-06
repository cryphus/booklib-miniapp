from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AIContextType,
    AIConversation,
    AIMessage,
    AIMessageSource,
    AIUsage,
    Entry,
    EntryEmbedding,
    MessageRole,
    UserBook,
)


class AIRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- embeddings ----------

    async def upsert_embedding(
        self,
        *,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        model: str,
        document: str,
        embedding: list[float],
    ) -> EntryEmbedding:
        stmt = select(EntryEmbedding).where(EntryEmbedding.entry_id == entry_id)
        row = (await self.session.execute(stmt)).scalars().first()
        if row is None:
            row = EntryEmbedding(
                entry_id=entry_id,
                user_id=user_id,
                model=model,
                document=document,
                embedding=embedding,
            )
            self.session.add(row)
        else:
            row.model = model
            row.document = document
            row.embedding = embedding
        await self.session.flush()
        return row

    async def delete_embedding(self, entry_id: uuid.UUID) -> None:
        await self.session.execute(delete(EntryEmbedding).where(EntryEmbedding.entry_id == entry_id))

    async def candidate_embeddings(
        self,
        user_id: uuid.UUID,
        *,
        context_type: AIContextType,
        user_book_id: uuid.UUID | None = None,
    ) -> list[tuple[EntryEmbedding, Entry]]:
        """Every retrieval path is scoped by user_id in SQL, never in Python only."""
        stmt = (
            select(EntryEmbedding, Entry)
            .join(Entry, Entry.id == EntryEmbedding.entry_id)
            .where(EntryEmbedding.user_id == user_id, Entry.user_id == user_id)
            .options(selectinload(Entry.tags))
        )
        if context_type == AIContextType.current_book and user_book_id is not None:
            stmt = stmt.where(Entry.user_book_id == user_book_id)
        elif context_type == AIContextType.favorites:
            favorite_books = select(UserBook.id).where(
                UserBook.user_id == user_id, UserBook.is_favorite.is_(True)
            )
            stmt = stmt.where(Entry.is_favorite.is_(True) | Entry.user_book_id.in_(favorite_books))
        return list((await self.session.execute(stmt)).all())

    # ---------- conversations ----------

    async def get_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> AIConversation | None:
        stmt = select(AIConversation).where(
            AIConversation.id == conversation_id, AIConversation.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_conversation_with_messages(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> AIConversation | None:
        stmt = (
            select(AIConversation)
            .where(AIConversation.id == conversation_id, AIConversation.user_id == user_id)
            .options(selectinload(AIConversation.messages).selectinload(AIMessage.sources))
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def create_conversation(
        self,
        user_id: uuid.UUID,
        *,
        title: str,
        context_type: AIContextType,
        context_user_book_id: uuid.UUID | None = None,
    ) -> AIConversation:
        conversation = AIConversation(
            user_id=user_id,
            title=title[:255],
            context_type=context_type,
            context_user_book_id=context_user_book_id,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def list_conversations(
        self, user_id: uuid.UUID, *, limit: int = 30, offset: int = 0
    ) -> tuple[list[AIConversation], int]:
        base = select(AIConversation).where(AIConversation.user_id == user_id)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        stmt = base.order_by(AIConversation.updated_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def delete_conversation(self, conversation: AIConversation) -> None:
        await self.session.delete(conversation)
        await self.session.flush()

    async def add_message(
        self,
        conversation: AIConversation,
        *,
        role: MessageRole,
        content: str,
        sources: list[tuple[uuid.UUID, float | None]] | None = None,
    ) -> AIMessage:
        message = AIMessage(conversation_id=conversation.id, role=role, content=content)
        self.session.add(message)
        await self.session.flush()
        for entry_id, score in sources or []:
            self.session.add(
                AIMessageSource(message_id=message.id, entry_id=entry_id, relevance_score=score)
            )
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def last_messages(self, conversation_id: uuid.UUID, limit: int = 6) -> list[AIMessage]:
        stmt = (
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return list(reversed(rows))

    async def message_count(self, conversation_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
        )
        return (await self.session.execute(stmt)).scalar_one()

    # ---------- usage ----------

    async def get_usage(self, user_id: uuid.UUID, period_start: datetime) -> AIUsage | None:
        stmt = select(AIUsage).where(
            AIUsage.user_id == user_id, AIUsage.period_start == period_start
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def create_usage(
        self, user_id: uuid.UUID, period_start: datetime, period_end: datetime
    ) -> AIUsage:
        usage = AIUsage(user_id=user_id, period_start=period_start, period_end=period_end, used=0)
        self.session.add(usage)
        await self.session.flush()
        return usage
