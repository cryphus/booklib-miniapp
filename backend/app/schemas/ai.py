from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

ContextType = Literal["all_library", "current_book", "favorites"]


class AISourceOut(BaseModel):
    entry_id: uuid.UUID
    user_book_id: uuid.UUID
    book_id: uuid.UUID
    book_title: str
    book_cover_url: str | None = None
    entry_type: Literal["quote", "note"]
    chapter: str | None = None
    page: str | None = None
    snippet: str
    relevance_score: float | None = None


class AIMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[AISourceOut] = []
    created_at: datetime


class AIConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    context_type: ContextType
    context_user_book_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None
    messages_count: int = 0


class AIConversationDetail(AIConversationOut):
    messages: list[AIMessageOut] = []


class AIConversationCreate(BaseModel):
    context_type: ContextType = "all_library"
    context_user_book_id: uuid.UUID | None = None
    title: str | None = Field(None, max_length=255)


class AIAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context_type: ContextType | None = None
    context_user_book_id: uuid.UUID | None = None

    @field_validator("question")
    @classmethod
    def _check_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        if len(v) > settings.AI_MAX_QUESTION_LENGTH:
            raise ValueError(f"question must be at most {settings.AI_MAX_QUESTION_LENGTH} characters")
        return v


class AIAskResponse(BaseModel):
    conversation_id: uuid.UUID
    message: AIMessageOut
    status: Literal["ok", "not_enough_context"] = "ok"
    usage: "AIUsageBrief"


class AIUsageBrief(BaseModel):
    plan: str
    used: int
    limit: int
    remaining: int
    period_end: datetime


AIAskResponse.model_rebuild()
