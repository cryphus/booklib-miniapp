from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.errors import ValidationError
from app.core.rate_limit import rate_limit
from app.schemas.book import (
    AddBookFromCatalog,
    BookSearchItem,
    CategoryOut,
    ManualBookCreate,
    UploadOut,
    UserBookOut,
    UserBookUpdate,
)
from app.schemas.common import MAX_PAGE_SIZE, OkResponse, Page
from app.services.library_service import LibraryService
from app.services.storage import get_storage, sniff_image_mime

router = APIRouter(tags=["library"])


@router.get(
    "/books/search",
    response_model=list[BookSearchItem],
    dependencies=[Depends(rate_limit("book_search", limit=30, window_seconds=60))],
)
async def search_books(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=40)] = 20,
) -> list[BookSearchItem]:
    """Google Books first, Open Library as a top-up. Results share one normalized shape."""
    results = await LibraryService(session).search_catalog(q, limit=limit)
    return [BookSearchItem(**r.to_dict()) for r in results]


@router.post("/books", response_model=UserBookOut, status_code=201)
async def add_book(
    payload: AddBookFromCatalog, user: CurrentUser, session: SessionDep
) -> UserBookOut:
    service = LibraryService(session)
    user_book = await service.add_from_catalog(user.id, payload)
    return await service.get_user_book(user.id, user_book.id)


@router.post("/books/manual", response_model=UserBookOut, status_code=201)
async def add_manual_book(
    payload: ManualBookCreate, user: CurrentUser, session: SessionDep
) -> UserBookOut:
    service = LibraryService(session)
    user_book = await service.add_manual(user.id, payload)
    return await service.get_user_book(user.id, user_book.id)


@router.post(
    "/books/cover",
    response_model=UploadOut,
    dependencies=[Depends(rate_limit("upload", limit=20, window_seconds=300))],
)
async def upload_cover(
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> UploadOut:
    """Cover upload for manually added books. Size and real MIME are both validated."""
    data = await file.read(settings.UPLOAD_MAX_BYTES + 1)
    if len(data) > settings.UPLOAD_MAX_BYTES:
        raise ValidationError("File is too large", code="FILE_TOO_LARGE")
    mime = sniff_image_mime(data)
    if mime is None:
        raise ValidationError("Only JPEG, PNG, WebP and GIF images are allowed", code="UNSUPPORTED_MEDIA_TYPE")
    stored = await get_storage().save(data, content_type=mime, prefix="covers")
    return UploadOut(
        url=stored.url, key=stored.key, size=stored.size, content_type=stored.content_type
    )


@router.get("/library", response_model=Page[UserBookOut])
async def list_library(
    user: CurrentUser,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    category: str | None = None,
    favorite: bool | None = None,
    search: str | None = None,
    sort: Literal["recent", "oldest", "title"] = "recent",
) -> Page[UserBookOut]:
    items, total = await LibraryService(session).list_library(
        user.id,
        category=category,
        favorite=favorite,
        search=search,
        sort=sort,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get("/library/categories", response_model=list[CategoryOut])
async def list_categories(user: CurrentUser, session: SessionDep) -> list[CategoryOut]:
    return await LibraryService(session).list_categories(user.id)


@router.get("/library/{user_book_id}", response_model=UserBookOut)
async def get_user_book(
    user_book_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> UserBookOut:
    return await LibraryService(session).get_user_book(user.id, user_book_id)


@router.patch("/library/{user_book_id}", response_model=UserBookOut)
async def update_user_book(
    user_book_id: uuid.UUID,
    payload: UserBookUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> UserBookOut:
    return await LibraryService(session).update_user_book(
        user.id, user_book_id, category=payload.category, is_favorite=payload.is_favorite
    )


@router.delete("/library/{user_book_id}", response_model=OkResponse)
async def delete_user_book(
    user_book_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> OkResponse:
    await LibraryService(session).remove_user_book(user.id, user_book_id)
    return OkResponse()
