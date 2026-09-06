from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AILimitReachedError, ForbiddenError, NotFoundError, ProviderError
from app.core.logging import logger
from app.integrations.ai import ChatMessage, get_embedding_provider, get_llm_provider
from app.models import AIContextType, Entry, MessageRole
from app.repositories import AIRepository, BookRepository, EntryRepository
from app.schemas.ai import (
    AIAskResponse,
    AIConversationDetail,
    AIConversationOut,
    AIMessageOut,
    AISourceOut,
    AIUsageBrief,
)
from app.services.billing_service import BillingService
from app.services.prompts import (
    NOT_ENOUGH_CONTEXT_ANSWER,
    SYSTEM_PROMPT,
    build_context_block,
    build_conversation_title,
    build_user_prompt,
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class RetrievedSource:
    entry: Entry
    score: float
    book_title: str
    book_id: uuid.UUID
    book_cover_url: str | None
    authors: list[str]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class AIService:
    """RAG over the user's own library. Nothing outside `user_id` can ever enter the context."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ai = AIRepository(session)
        self.entries = EntryRepository(session)
        self.books = BookRepository(session)
        self.billing = BillingService(session)

    # ---------- conversations ----------

    async def list_conversations(
        self, user_id: uuid.UUID, *, limit: int = 30, offset: int = 0
    ) -> tuple[list[AIConversationOut], int]:
        conversations, total = await self.ai.list_conversations(
            user_id, limit=limit, offset=offset
        )
        result = []
        for conversation in conversations:
            messages = await self.ai.last_messages(conversation.id, limit=1)
            result.append(
                AIConversationOut(
                    id=conversation.id,
                    title=conversation.title,
                    context_type=conversation.context_type.value,
                    context_user_book_id=conversation.context_user_book_id,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    last_message=messages[0].content if messages else None,
                    messages_count=await self.ai.message_count(conversation.id),
                )
            )
        return result, total

    async def get_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> AIConversationDetail:
        conversation = await self.ai.get_conversation_with_messages(user_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found", code="CONVERSATION_NOT_FOUND")
        messages = []
        for message in conversation.messages:
            source_entry_ids = [s.entry_id for s in message.sources]
            scores = {s.entry_id: s.relevance_score for s in message.sources}
            sources = await self._sources_for_entry_ids(user_id, source_entry_ids, scores)
            messages.append(
                AIMessageOut(
                    id=message.id,
                    role=message.role.value,
                    content=message.content,
                    sources=sources,
                    created_at=message.created_at,
                )
            )
        return AIConversationDetail(
            id=conversation.id,
            title=conversation.title,
            context_type=conversation.context_type.value,
            context_user_book_id=conversation.context_user_book_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message=messages[-1].content if messages else None,
            messages_count=len(messages),
            messages=messages,
        )

    async def create_conversation(
        self,
        user_id: uuid.UUID,
        *,
        context_type: str = "all_library",
        context_user_book_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> AIConversationOut:
        ctx = await self._validate_context(user_id, context_type, context_user_book_id)
        conversation = await self.ai.create_conversation(
            user_id,
            title=title or "Новый диалог",
            context_type=ctx[0],
            context_user_book_id=ctx[1],
        )
        return AIConversationOut(
            id=conversation.id,
            title=conversation.title,
            context_type=conversation.context_type.value,
            context_user_book_id=conversation.context_user_book_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages_count=0,
        )

    async def delete_conversation(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        conversation = await self.ai.get_conversation(user_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found", code="CONVERSATION_NOT_FOUND")
        await self.ai.delete_conversation(conversation)

    async def _validate_context(
        self, user_id: uuid.UUID, context_type: str, user_book_id: uuid.UUID | None
    ) -> tuple[AIContextType, uuid.UUID | None]:
        try:
            ctx = AIContextType(context_type)
        except ValueError as exc:
            raise ForbiddenError("Unknown AI context", code="INVALID_CONTEXT") from exc
        if ctx == AIContextType.current_book:
            if user_book_id is None:
                raise ForbiddenError(
                    "context_user_book_id is required for current_book", code="INVALID_CONTEXT"
                )
            # Resolving through the user-scoped repository rejects another user's UUID.
            user_book = await self.books.get_user_book(user_id, user_book_id)
            if user_book is None:
                raise NotFoundError("Book not found in your library", code="BOOK_NOT_FOUND")
            return ctx, user_book.id
        return ctx, None

    # ---------- the ask pipeline ----------

    async def ask(
        self,
        user_id: uuid.UUID,
        question: str,
        *,
        conversation_id: uuid.UUID | None = None,
        context_type: str | None = None,
        context_user_book_id: uuid.UUID | None = None,
    ) -> AIAskResponse:
        # 1. quota, checked server-side only
        quota = await self.billing.get_ai_quota(user_id)
        if quota.remaining <= 0:
            raise AILimitReachedError(
                f"You have used all {quota.limit} AI requests for this period"
            )

        # 2. resolve the conversation and its context
        conversation = None
        if conversation_id is not None:
            conversation = await self.ai.get_conversation(user_id, conversation_id)
            if conversation is None:
                raise NotFoundError("Conversation not found", code="CONVERSATION_NOT_FOUND")

        if conversation is None:
            ctx_type, ctx_book = await self._validate_context(
                user_id, context_type or "all_library", context_user_book_id
            )
            conversation = await self.ai.create_conversation(
                user_id,
                title=build_conversation_title(question),
                context_type=ctx_type,
                context_user_book_id=ctx_book,
            )
        elif context_type is not None:
            ctx_type, ctx_book = await self._validate_context(
                user_id, context_type, context_user_book_id
            )
            conversation.context_type = ctx_type
            conversation.context_user_book_id = ctx_book
            await self.session.flush()

        await self.ai.add_message(conversation, role=MessageRole.user, content=question)

        # 3. retrieval (user-scoped in SQL) - the AI request is only charged after this
        sources = await self.retrieve(
            user_id,
            question,
            context_type=conversation.context_type,
            user_book_id=conversation.context_user_book_id,
        )

        if not sources:
            message = await self.ai.add_message(
                conversation, role=MessageRole.assistant, content=NOT_ENOUGH_CONTEXT_ANSWER
            )
            # No LLM call happened, so nothing is charged.
            return AIAskResponse(
                conversation_id=conversation.id,
                status="not_enough_context",
                message=AIMessageOut(
                    id=message.id,
                    role="assistant",
                    content=message.content,
                    sources=[],
                    created_at=message.created_at,
                ),
                usage=self._usage_brief(quota),
            )

        # 4. ask the LLM
        history = await self._history_lines(conversation.id)
        context_payload = [self._source_payload(s) for s in sources]
        prompt = build_user_prompt(question, build_context_block(context_payload), history)
        try:
            response = await get_llm_provider().complete(
                [
                    ChatMessage(role="system", content=SYSTEM_PROMPT),
                    ChatMessage(role="user", content=prompt),
                ],
                json_mode=True,
            )
        except ProviderError:
            # Nothing is charged when the provider fails before producing a result.
            raise

        answer, cited_ids = self._parse_answer(response.content, {str(s.entry.id) for s in sources})

        # 5. charge only after a successful answer
        await self.billing.consume_ai_request(user_id)
        quota = await self.billing.get_ai_quota(user_id)

        used_sources = [s for s in sources if str(s.entry.id) in cited_ids] or sources
        message = await self.ai.add_message(
            conversation,
            role=MessageRole.assistant,
            content=answer,
            sources=[(s.entry.id, s.score) for s in used_sources],
        )
        conversation.title = conversation.title or build_conversation_title(question)
        await self.session.flush()

        return AIAskResponse(
            conversation_id=conversation.id,
            status="ok",
            message=AIMessageOut(
                id=message.id,
                role="assistant",
                content=answer,
                sources=[self._source_dto(s) for s in used_sources],
                created_at=message.created_at,
            ),
            usage=self._usage_brief(quota),
        )

    async def retrieve(
        self,
        user_id: uuid.UUID,
        question: str,
        *,
        context_type: AIContextType = AIContextType.all_library,
        user_book_id: uuid.UUID | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedSource]:
        """Vector search restricted to this user's entries.

        On PostgreSQL the candidate set comes from pgvector; scoring is done here so the
        same code path also works on the SQLite database used by the test suite.
        """
        top_k = top_k or settings.AI_TOP_K
        try:
            query_vector = await get_embedding_provider().embed_one(question)
        except ProviderError:
            raise

        rows = await self.ai.candidate_embeddings(
            user_id, context_type=context_type, user_book_id=user_book_id
        )
        if not rows:
            return []

        scored: list[tuple[float, Entry]] = []
        for embedding_row, entry in rows:
            if entry.user_id != user_id:  # belt and braces on top of the SQL filter
                logger.error("ai_context_leak_prevented entry_id=%s", entry.id)
                continue
            scored.append((cosine_similarity(query_vector, embedding_row.embedding), entry))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        selected = [pair for pair in scored[:top_k] if pair[0] >= settings.AI_MIN_RELEVANCE]
        if not selected:
            return []

        entries = [entry for _score, entry in selected]
        books = await self.entries.books_for_entries(entries)
        sources: list[RetrievedSource] = []
        for score, entry in selected:
            pair = books.get(entry.user_book_id)
            if pair is None:
                continue
            _user_book, book = pair
            sources.append(
                RetrievedSource(
                    entry=entry,
                    score=round(float(score), 4),
                    book_title=book.title,
                    book_id=book.id,
                    book_cover_url=book.cover_url,
                    authors=list(book.authors or []),
                )
            )
        return sources

    # ---------- helpers ----------

    async def _history_lines(self, conversation_id: uuid.UUID, limit: int = 6) -> list[str]:
        messages = await self.ai.last_messages(conversation_id, limit=limit)
        return [f"{m.role.value}: {m.content}" for m in messages[:-1]]

    @staticmethod
    def _source_payload(source: RetrievedSource) -> dict:
        entry = source.entry
        return {
            "entry_id": str(entry.id),
            "book_title": source.book_title,
            "authors": source.authors,
            "chapter": entry.chapter,
            "page": entry.page,
            "tags": [t.name for t in entry.tags],
            "entry_type": entry.type.value if hasattr(entry.type, "value") else str(entry.type),
            "content": entry.content,
            "personal_note": entry.personal_note,
        }

    @staticmethod
    def _source_dto(source: RetrievedSource) -> AISourceOut:
        entry = source.entry
        snippet = entry.content.strip()
        if len(snippet) > 240:
            snippet = snippet[:240].rstrip() + "…"
        return AISourceOut(
            entry_id=entry.id,
            user_book_id=entry.user_book_id,
            book_id=source.book_id,
            book_title=source.book_title,
            book_cover_url=source.book_cover_url,
            entry_type=entry.type.value if hasattr(entry.type, "value") else str(entry.type),
            chapter=entry.chapter,
            page=entry.page,
            snippet=snippet,
            relevance_score=source.score,
        )

    async def _sources_for_entry_ids(
        self,
        user_id: uuid.UUID,
        entry_ids: list[uuid.UUID],
        scores: dict[uuid.UUID, float | None] | None = None,
    ) -> list[AISourceOut]:
        if not entry_ids:
            return []
        entries = await self.entries.get_many(user_id, entry_ids)
        books = await self.entries.books_for_entries(entries)
        out: list[AISourceOut] = []
        for entry in entries:
            pair = books.get(entry.user_book_id)
            if pair is None:
                continue
            _user_book, book = pair
            out.append(
                self._source_dto(
                    RetrievedSource(
                        entry=entry,
                        score=(scores or {}).get(entry.id) or 0.0,
                        book_title=book.title,
                        book_id=book.id,
                        book_cover_url=book.cover_url,
                        authors=list(book.authors or []),
                    )
                )
            )
        return out

    @staticmethod
    def _parse_answer(raw: str, allowed_ids: set[str]) -> tuple[str, set[str]]:
        """Parses the model envelope and drops any source id that was not in the context."""
        answer = raw.strip()
        cited: set[str] = set()
        match = _JSON_BLOCK.search(raw)
        if match:
            try:
                data = json.loads(match.group(0))
                answer = str(data.get("answer") or "").strip() or answer
                for value in data.get("source_ids") or []:
                    candidate = str(value).strip()
                    if candidate in allowed_ids:
                        cited.add(candidate)
                    else:
                        logger.warning("llm_cited_unknown_source id=%s", candidate[:64])
            except (json.JSONDecodeError, TypeError, AttributeError):
                logger.warning("llm_answer_not_json")
        return answer, cited

    @staticmethod
    def _usage_brief(quota) -> AIUsageBrief:
        return AIUsageBrief(
            plan=quota.plan,
            used=quota.used,
            limit=quota.limit,
            remaining=quota.remaining,
            period_end=quota.period_end,
        )
