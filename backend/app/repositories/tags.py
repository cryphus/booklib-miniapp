from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry, EntryTag, Tag

_WS = re.compile(r"\s+")


def normalize_tag(name: str) -> str:
    """Case- and whitespace-insensitive key, so "Money", "money" and " MONEY " collapse to one tag."""
    return _WS.sub(" ", name.strip().lower())


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, user_id: uuid.UUID, name: str) -> Tag | None:
        display = _WS.sub(" ", name.strip())
        if not display:
            return None
        normalized = normalize_tag(display)
        stmt = select(Tag).where(Tag.user_id == user_id, Tag.normalized_name == normalized)
        tag = (await self.session.execute(stmt)).scalars().first()
        if tag:
            return tag
        tag = Tag(user_id=user_id, name=display, normalized_name=normalized)
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def list_for_user(self, user_id: uuid.UUID, query: str | None = None) -> list[Tag]:
        stmt = select(Tag).where(Tag.user_id == user_id)
        if query:
            stmt = stmt.where(Tag.normalized_name.like(f"%{normalize_tag(query)}%"))
        return list((await self.session.execute(stmt.order_by(Tag.name))).scalars().all())

    async def counts(self, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        stmt = (
            select(EntryTag.tag_id, func.count())
            .join(Tag, Tag.id == EntryTag.tag_id)
            .where(Tag.user_id == user_id)
            .group_by(EntryTag.tag_id)
        )
        return dict((await self.session.execute(stmt)).all())

    async def search(self, user_id: uuid.UUID, query: str, limit: int = 10) -> list[Tag]:
        stmt = (
            select(Tag)
            .where(Tag.user_id == user_id, Tag.normalized_name.like(f"%{normalize_tag(query)}%"))
            .order_by(Tag.name)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def set_entry_tags(self, entry: Entry, names: list[str]) -> list[Tag]:
        """Replaces the tag set of one entry, de-duplicating by normalized name."""
        seen: set[str] = set()
        tags: list[Tag] = []
        for raw in names:
            normalized = normalize_tag(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tag = await self.get_or_create(entry.user_id, raw)
            if tag:
                tags.append(tag)
        # Load the current collection first: assigning to an unloaded relationship
        # would trigger a lazy load, which async sessions do not allow.
        await self.session.refresh(entry, ["tags"])
        entry.tags = tags
        await self.session.flush()
        return tags

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Tag).where(Tag.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one()
