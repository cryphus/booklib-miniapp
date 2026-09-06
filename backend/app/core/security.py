from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.errors import UnauthorizedError

ALGORITHM = "HS256"


def create_access_token(user_id: uuid.UUID, ttl_hours: int | None = None) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=ttl_hours or settings.ACCESS_TOKEN_TTL_HOURS
    )
    payload = {
        "sub": str(user_id),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires_at.timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM), expires_at


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Session expired", code="TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid session token") from exc
    if payload.get("typ") != "access":
        raise UnauthorizedError("Invalid session token")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid session token") from exc
