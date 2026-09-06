from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, SessionDep
from app.core.rate_limit import rate_limit
from app.schemas.ai import (
    AIAskRequest,
    AIAskResponse,
    AIConversationCreate,
    AIConversationDetail,
    AIConversationOut,
)
from app.schemas.common import OkResponse, Page
from app.schemas.user import AIUsageOut
from app.services.ai_service import AIService
from app.services.billing_service import BillingService

router = APIRouter(prefix="/ai", tags=["ai"])

ask_rate_limit = Depends(rate_limit("ai_ask", limit=20, window_seconds=60))


@router.get("/usage", response_model=AIUsageOut)
async def ai_usage(user: CurrentUser, session: SessionDep) -> AIUsageOut:
    """The only place the AI limit is defined; the frontend must not hardcode it."""
    quota = await BillingService(session).get_ai_quota(user.id)
    return AIUsageOut(
        plan=quota.plan,
        used=quota.used,
        limit=quota.limit,
        remaining=quota.remaining,
        period_end=quota.period_end,
    )


@router.get("/conversations", response_model=Page[AIConversationOut])
async def list_conversations(
    user: CurrentUser,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 30,
) -> Page[AIConversationOut]:
    items, total = await AIService(session).list_conversations(
        user.id, limit=page_size, offset=(page - 1) * page_size
    )
    return Page(
        items=items, total=total, page=page, page_size=page_size, has_more=page * page_size < total
    )


@router.post("/conversations", response_model=AIConversationOut, status_code=201)
async def create_conversation(
    payload: AIConversationCreate, user: CurrentUser, session: SessionDep
) -> AIConversationOut:
    return await AIService(session).create_conversation(
        user.id,
        context_type=payload.context_type,
        context_user_book_id=payload.context_user_book_id,
        title=payload.title,
    )


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> AIConversationDetail:
    return await AIService(session).get_conversation(user.id, conversation_id)


@router.delete("/conversations/{conversation_id}", response_model=OkResponse)
async def delete_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> OkResponse:
    await AIService(session).delete_conversation(user.id, conversation_id)
    return OkResponse()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AIAskResponse,
    dependencies=[ask_rate_limit],
)
async def ask_in_conversation(
    conversation_id: uuid.UUID,
    payload: AIAskRequest,
    user: CurrentUser,
    session: SessionDep,
) -> AIAskResponse:
    return await AIService(session).ask(
        user.id,
        payload.question,
        conversation_id=conversation_id,
        context_type=payload.context_type,
        context_user_book_id=payload.context_user_book_id,
    )


@router.post("/ask", response_model=AIAskResponse, dependencies=[ask_rate_limit])
async def ask(payload: AIAskRequest, user: CurrentUser, session: SessionDep) -> AIAskResponse:
    """Starts a new conversation and answers in one call."""
    return await AIService(session).ask(
        user.id,
        payload.question,
        context_type=payload.context_type,
        context_user_book_id=payload.context_user_book_id,
    )
