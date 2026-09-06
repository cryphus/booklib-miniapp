from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

MAX_TITLE = 512


class BookSearchItem(BaseModel):
    source: str
    source_id: str
    title: str
    subtitle: str | None = None
    authors: list[str] = []
    description: str | None = None
    isbn_10: str | None = None
    isbn_13: str | None = None
    published_year: int | None = None
    publisher: str | None = None
    cover_url: str | None = None
    categories: list[str] = []


class BookOut(ORMModel):
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    authors: list[str] = []
    description: str | None = None
    isbn_10: str | None = None
    isbn_13: str | None = None
    published_year: int | None = None
    publisher: str | None = None
    cover_url: str | None = None
    source: str

    @field_validator("authors", mode="before")
    @classmethod
    def _authors(cls, v):
        return list(v or [])


class CategoryOut(ORMModel):
    id: uuid.UUID
    name: str


class UserBookOut(BaseModel):
    id: uuid.UUID
    book: BookOut
    category: CategoryOut | None = None
    is_favorite: bool
    entries_count: int = 0
    quotes_count: int = 0
    notes_count: int = 0
    created_at: datetime
    updated_at: datetime


class AddBookFromCatalog(BaseModel):
    source: str = Field(..., max_length=32)
    source_id: str = Field(..., max_length=128)
    title: str = Field(..., min_length=1, max_length=MAX_TITLE)
    subtitle: str | None = Field(None, max_length=MAX_TITLE)
    authors: list[str] = Field(default_factory=list, max_length=20)
    description: str | None = Field(None, max_length=20000)
    isbn_10: str | None = Field(None, max_length=16)
    isbn_13: str | None = Field(None, max_length=20)
    published_year: int | None = Field(None, ge=0, le=2200)
    publisher: str | None = Field(None, max_length=256)
    cover_url: str | None = Field(None, max_length=1024)
    category: str | None = Field(None, max_length=64)


class ManualBookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE)
    authors: list[str] = Field(default_factory=list, max_length=20)
    description: str | None = Field(None, max_length=20000)
    cover_url: str | None = Field(None, max_length=1024)
    published_year: int | None = Field(None, ge=0, le=2200)
    category: str | None = Field(None, max_length=64)


class UserBookUpdate(BaseModel):
    category: str | None = Field(None, max_length=64)
    is_favorite: bool | None = None


class UploadOut(BaseModel):
    url: str
    key: str
    size: int
    content_type: str
