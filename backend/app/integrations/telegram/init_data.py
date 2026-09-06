"""Telegram Mini Apps initData verification.

The signature is validated here, server-side. Nothing that arrives as a plain JSON
field from the frontend (telegram_id, username, is_premium, ...) is ever trusted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl

from app.core.errors import UnauthorizedError


@dataclass
class TelegramUser:
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool = False
    photo_url: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class TelegramInitData:
    user: TelegramUser
    auth_date: int
    query_id: str | None = None
    start_param: str | None = None


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def verify_init_data(
    init_data: str, bot_token: str, *, max_age_seconds: int | None = 86400
) -> TelegramInitData:
    """Validate the HMAC of a raw initData query string and return its parsed payload."""
    if not bot_token:
        raise UnauthorizedError("Telegram authentication is not configured", code="TELEGRAM_NOT_CONFIGURED")
    if not init_data:
        raise UnauthorizedError("initData is missing", code="INVALID_INIT_DATA")

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True, keep_blank_values=True))
    except ValueError as exc:
        raise UnauthorizedError("initData is malformed", code="INVALID_INIT_DATA") from exc

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise UnauthorizedError("initData signature is missing", code="INVALID_INIT_DATA")

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    expected = hmac.new(
        _secret_key(bot_token), data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise UnauthorizedError("initData signature is invalid", code="INVALID_INIT_DATA")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise UnauthorizedError("initData auth_date is invalid", code="INVALID_INIT_DATA") from exc

    if max_age_seconds and auth_date and (time.time() - auth_date) > max_age_seconds:
        raise UnauthorizedError("initData has expired", code="INIT_DATA_EXPIRED")

    raw_user = pairs.get("user")
    if not raw_user:
        raise UnauthorizedError("initData has no user", code="INVALID_INIT_DATA")
    try:
        user_dict = json.loads(raw_user)
        telegram_id = int(user_dict["id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("initData user payload is invalid", code="INVALID_INIT_DATA") from exc

    user = TelegramUser(
        id=telegram_id,
        first_name=user_dict.get("first_name"),
        last_name=user_dict.get("last_name"),
        username=user_dict.get("username"),
        language_code=user_dict.get("language_code"),
        is_premium=bool(user_dict.get("is_premium", False)),
        photo_url=user_dict.get("photo_url"),
        raw=user_dict,
    )
    return TelegramInitData(
        user=user,
        auth_date=auth_date,
        query_id=pairs.get("query_id"),
        start_param=pairs.get("start_param"),
    )


def build_init_data(bot_token: str, user: dict, *, auth_date: int | None = None) -> str:
    """Test/seed helper: produce a correctly signed initData string."""
    from urllib.parse import urlencode

    pairs = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAF_test",
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    pairs["hash"] = hmac.new(
        _secret_key(bot_token), data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(pairs)
