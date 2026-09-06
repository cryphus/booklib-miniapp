from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.errors import ForbiddenError
from app.core.rate_limit import rate_limit
from app.schemas.auth import AuthResponse, DevAuthRequest, TelegramAuthRequest
from app.services.auth_service import AuthService
from app.services.billing_service import BillingService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/telegram",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("auth", limit=20, window_seconds=60))],
)
async def telegram_auth(payload: TelegramAuthRequest, session: SessionDep) -> AuthResponse:
    """Exchanges a signed Telegram initData string for a Remarka session token."""
    result = await AuthService(session).authenticate_telegram(payload.init_data)
    await BillingService(session).ensure_plans()
    return AuthResponse(
        access_token=result.access_token,
        expires_at=result.expires_at,
        is_new_user=result.is_new_user,
    )


async def dev_auth(payload: DevAuthRequest, session: SessionDep) -> AuthResponse:
    """Development-only login so the frontend can run outside Telegram.

    The route is not registered at all unless APP_ENV is development or test, and the
    service layer refuses the call a second time.
    """
    if not settings.is_development:
        raise ForbiddenError("Dev auth is disabled", code="DEV_AUTH_DISABLED")
    result = await AuthService(session).authenticate_dev(
        payload.telegram_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        language_code=payload.language_code,
    )
    await BillingService(session).ensure_plans()
    return AuthResponse(
        access_token=result.access_token,
        expires_at=result.expires_at,
        is_new_user=result.is_new_user,
    )


# Registered only outside production, so no endpoint that can forge a Telegram user
# exists in a production deployment at all.
if settings.is_development:
    router.add_api_route(
        "/dev",
        dev_auth,
        methods=["POST"],
        response_model=AuthResponse,
        dependencies=[Depends(rate_limit("auth", limit=20, window_seconds=60))],
        tags=["auth"],
    )
