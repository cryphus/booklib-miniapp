from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import OkResponse
from app.schemas.user import MeOut, MeUpdate, PreferencesOut, PreferencesUpdate, StatsOut
from app.services.user_service import UserService

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut)
async def get_me(user: CurrentUser, session: SessionDep) -> MeOut:
    return await UserService(session).get_me(user)


@router.patch("", response_model=MeOut)
async def update_me(payload: MeUpdate, user: CurrentUser, session: SessionDep) -> MeOut:
    return await UserService(session).update_me(
        user, onboarding_completed=payload.onboarding_completed
    )


@router.get("/stats", response_model=StatsOut)
async def get_stats(user: CurrentUser, session: SessionDep) -> StatsOut:
    return await UserService(session).stats(user.id)


@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(user: CurrentUser, session: SessionDep) -> PreferencesOut:
    return await UserService(session).get_preferences(user.id)


@router.put("/preferences", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesUpdate, user: CurrentUser, session: SessionDep
) -> PreferencesOut:
    return await UserService(session).update_preferences(user.id, payload)


@router.delete("", response_model=OkResponse)
async def delete_account(user: CurrentUser, session: SessionDep) -> OkResponse:
    """Irreversibly deletes the account and all of its data in one transaction."""
    await UserService(session).delete_account(user)
    return OkResponse()
