from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User
from app.repositories import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_current_user(
    request: Request,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Authorization header is missing")
    token = authorization.split(" ", 1)[1].strip()
    user_id = decode_access_token(token)

    user = await UserRepository(session).get(user_id)
    if user is None:
        raise UnauthorizedError("Session user no longer exists")
    if not user.is_active:
        raise ForbiddenError("Account is disabled", code="ACCOUNT_DISABLED")

    # Lets the rate limiter key on the user rather than the shared Telegram egress IP.
    request.state.user_id = str(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
