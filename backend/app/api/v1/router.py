from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import ai, auth, billing, entries, legal, library, me, search, tags

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(library.router)
api_router.include_router(entries.router)
api_router.include_router(tags.router)
api_router.include_router(search.router)
api_router.include_router(ai.router)
api_router.include_router(billing.router)
api_router.include_router(legal.router)
