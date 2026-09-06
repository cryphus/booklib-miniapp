from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    """Only the raw signed string is accepted; individual user fields are never trusted."""

    init_data: str = Field(..., min_length=1, max_length=8192)


class DevAuthRequest(BaseModel):
    telegram_id: int = Field(..., gt=0)
    first_name: str = Field("Dev", max_length=128)
    last_name: str | None = Field(None, max_length=128)
    username: str | None = Field(None, max_length=128)
    language_code: str = Field("ru", max_length=16)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    is_new_user: bool
