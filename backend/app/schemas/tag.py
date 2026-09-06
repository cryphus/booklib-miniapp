from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

MAX_TAG_LENGTH = 64


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_TAG_LENGTH)


class TagWithCount(BaseModel):
    id: uuid.UUID
    name: str
    entries_count: int = 0
