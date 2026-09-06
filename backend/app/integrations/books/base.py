from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field


@dataclass
class BookSearchResult:
    """Normalized DTO. Every provider maps into this shape."""

    source: str
    source_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    subtitle: str | None = None
    description: str | None = None
    isbn_10: str | None = None
    isbn_13: str | None = None
    published_year: int | None = None
    publisher: str | None = None
    cover_url: str | None = None
    categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def dedup_key(self) -> str:
        if self.isbn_13:
            return f"isbn13:{self.isbn_13}"
        if self.isbn_10:
            return f"isbn10:{self.isbn_10}"
        norm_authors = ",".join(sorted(a.lower().strip() for a in self.authors))
        return f"title:{self.title.lower().strip()}|{norm_authors}"


class BookProvider(ABC):
    code: str

    @abstractmethod
    async def search(self, query: str, *, limit: int = 20) -> list[BookSearchResult]: ...

    @abstractmethod
    async def get_by_isbn(self, isbn: str) -> BookSearchResult | None: ...
