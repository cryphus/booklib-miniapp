from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.repositories import TagRepository
from app.schemas.tag import TagWithCount

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagWithCount])
async def list_tags(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=64)] = None,
) -> list[TagWithCount]:
    repo = TagRepository(session)
    tags = await repo.list_for_user(user.id, q)
    counts = await repo.counts(user.id)
    return [
        TagWithCount(id=t.id, name=t.name, entries_count=counts.get(t.id, 0)) for t in tags
    ]
