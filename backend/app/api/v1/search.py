from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, SessionDep
from app.core.rate_limit import rate_limit
from app.schemas.search import SearchResults
from app.services.search_service import SearchService

router = APIRouter(tags=["search"])


@router.get(
    "/search",
    response_model=SearchResults,
    dependencies=[Depends(rate_limit("global_search", limit=60, window_seconds=60))],
)
async def global_search(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResults:
    """Searches the user's books, quotes, notes and tags, grouped by kind."""
    return await SearchService(session).search(user.id, q, limit=limit)
