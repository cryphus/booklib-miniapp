from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import MAX_PAGE_SIZE, OkResponse, Page
from app.schemas.entry import EntryCreate, EntryOut, EntryUpdate, FavoriteUpdate
from app.services.entry_service import EntryService

router = APIRouter(tags=["entries"])


@router.get("/library/{user_book_id}/entries", response_model=Page[EntryOut])
async def list_book_entries(
    user_book_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    type: Literal["quote", "note"] | None = None,
    favorite: bool | None = None,
    tag: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> Page[EntryOut]:
    items, total = await EntryService(session).list_for_book(
        user.id,
        user_book_id,
        entry_type=type,
        favorite=favorite,
        tag=tag,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=items, total=total, page=page, page_size=page_size, has_more=page * page_size < total
    )


@router.post("/library/{user_book_id}/entries", response_model=EntryOut, status_code=201)
async def create_entry(
    user_book_id: uuid.UUID,
    payload: EntryCreate,
    user: CurrentUser,
    session: SessionDep,
) -> EntryOut:
    return await EntryService(session).create(user.id, user_book_id, payload)


@router.get("/entries", response_model=Page[EntryOut])
async def list_entries(
    user: CurrentUser,
    session: SessionDep,
    type: Literal["quote", "note"] | None = None,
    favorite: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> Page[EntryOut]:
    items, total = await EntryService(session).list_for_user(
        user.id,
        entry_type=type,
        favorite=favorite,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=items, total=total, page=page, page_size=page_size, has_more=page * page_size < total
    )


@router.get("/entries/{entry_id}", response_model=EntryOut)
async def get_entry(entry_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> EntryOut:
    return await EntryService(session).get(user.id, entry_id)


@router.patch("/entries/{entry_id}", response_model=EntryOut)
async def update_entry(
    entry_id: uuid.UUID, payload: EntryUpdate, user: CurrentUser, session: SessionDep
) -> EntryOut:
    return await EntryService(session).update(user.id, entry_id, payload)


@router.put("/entries/{entry_id}/favorite", response_model=EntryOut)
async def set_entry_favorite(
    entry_id: uuid.UUID, payload: FavoriteUpdate, user: CurrentUser, session: SessionDep
) -> EntryOut:
    return await EntryService(session).set_favorite(user.id, entry_id, payload.is_favorite)


@router.delete("/entries/{entry_id}", response_model=OkResponse)
async def delete_entry(entry_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> OkResponse:
    await EntryService(session).delete(user.id, entry_id)
    return OkResponse()
