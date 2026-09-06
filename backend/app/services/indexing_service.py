from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProviderError
from app.core.logging import logger
from app.models import Book, Entry, EntryType, UserBook
from app.repositories import AIRepository, EntryRepository
from app.services.prompts import build_embedding_document


class IndexingService:
    """Keeps the pgvector index in step with the entries table.

    Indexing never blocks the user: if the embedding provider is down the entry is still
    saved, and it can be re-indexed later with `reindex_user`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ai = AIRepository(session)
        self.entries = EntryRepository(session)

    async def index_entry(self, entry: Entry) -> bool:
        from app.integrations.ai import get_embedding_provider

        document = await self.build_document(entry)
        try:
            provider = get_embedding_provider()
            vector = await provider.embed_one(document)
        except ProviderError as exc:
            logger.warning("entry_index_skipped entry_id=%s reason=%s", entry.id, exc.code)
            return False
        await self.ai.upsert_embedding(
            entry_id=entry.id,
            user_id=entry.user_id,
            model=provider.model,
            document=document,
            embedding=vector,
        )
        return True

    async def remove_entry(self, entry_id: uuid.UUID) -> None:
        await self.ai.delete_embedding(entry_id)

    async def build_document(self, entry: Entry) -> str:
        # A just-created entry may not have its tag collection loaded yet, and lazy
        # loading is not allowed inside an async session.
        await self.session.refresh(entry, ["tags"])
        book: Book | None = None
        mapping = await self.entries.books_for_entries([entry])
        pair = mapping.get(entry.user_book_id)
        if pair:
            _user_book, book = pair
        return build_embedding_document(
            entry_type=entry.type.value if hasattr(entry.type, "value") else str(entry.type),
            book_title=book.title if book else None,
            authors=list(book.authors or []) if book else [],
            chapter=entry.chapter,
            page=entry.page,
            tags=[t.name for t in entry.tags],
            content=entry.content,
            personal_note=entry.personal_note,
        )

    async def reindex_user(self, user_id: uuid.UUID) -> int:
        """Rebuilds every embedding for one user. Used by the seed script and by ops."""
        indexed = 0
        offset = 0
        while True:
            entries, _total = await self.entries.list_for_user(user_id, limit=100, offset=offset)
            if not entries:
                break
            for entry in entries:
                if await self.index_entry(entry):
                    indexed += 1
            offset += len(entries)
        return indexed


def entry_type_label(entry_type: EntryType | str) -> str:
    value = entry_type.value if hasattr(entry_type, "value") else str(entry_type)
    return value


__all__ = ["IndexingService", "entry_type_label", "UserBook"]
