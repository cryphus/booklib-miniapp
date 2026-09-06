from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProfileOut(ORMModel):
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    language_code: str | None = None


class PreferencesOut(ORMModel):
    theme: Literal["system", "light", "dark"] = "system"
    language: str | None = None


class PreferencesUpdate(BaseModel):
    theme: Literal["system", "light", "dark"] | None = None
    language: str | None = Field(None, max_length=16)


class AIUsageOut(BaseModel):
    plan: str
    used: int
    limit: int
    remaining: int
    period_end: datetime


class MeOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    onboarding_completed: bool
    profile: ProfileOut
    preferences: PreferencesOut
    plan: str
    is_premium: bool
    ai_usage: AIUsageOut


class MeUpdate(BaseModel):
    onboarding_completed: bool | None = None


class StatsOut(BaseModel):
    books_count: int
    quotes_count: int
    notes_count: int
    entries_count: int
    favorites_count: int
    tags_count: int
