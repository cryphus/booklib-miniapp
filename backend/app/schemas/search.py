from __future__ import annotations

from pydantic import BaseModel

from app.schemas.book import UserBookOut
from app.schemas.entry import EntryOut


class SearchResults(BaseModel):
    query: str
    books: list[UserBookOut] = []
    quotes: list[EntryOut] = []
    notes: list[EntryOut] = []
    total: int = 0
