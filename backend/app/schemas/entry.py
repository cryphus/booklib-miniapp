from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_CONTENT = 10000
MAX_NOTE = 5000
MAX_TAGS_PER_ENTRY = 15


class TagOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class EntryBookOut(BaseModel):
    user_book_id: uuid.UUID
    book_id: uuid.UUID
    title: str
    authors: list[str] = []
    cover_url: str | None = None


class EntryOut(BaseModel):
    id: uuid.UUID
    user_book_id: uuid.UUID
    type: Literal["quote", "note"]
    content: str
    personal_note: str | None = None
    chapter: str | None = None
    page: str | None = None
    is_favorite: bool
    tags: list[TagOut] = []
    book: EntryBookOut | None = None
    created_at: datetime
    updated_at: datetime


class EntryCreate(BaseModel):
    type: Literal["quote", "note"]
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT)
    personal_note: str | None = Field(None, max_length=MAX_NOTE)
    chapter: str | None = Field(None, max_length=128)
    page: str | None = Field(None, max_length=32)
    is_favorite: bool = False
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS_PER_ENTRY)

    @field_validator("content")
    @classmethod
    def _strip_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be empty")
        return v


class EntryUpdate(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=MAX_CONTENT)
    personal_note: str | None = Field(None, max_length=MAX_NOTE)
    chapter: str | None = Field(None, max_length=128)
    page: str | None = Field(None, max_length=32)
    is_favorite: bool | None = None
    tags: list[str] | None = Field(None, max_length=MAX_TAGS_PER_ENTRY)


class FavoriteUpdate(BaseModel):
    is_favorite: bool
