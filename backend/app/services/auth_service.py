from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ForbiddenError
from app.core.security import create_access_token
from app.integrations.telegram import TelegramUser, verify_init_data
from app.models import User
from app.repositories import UserRepository

TELEGRAM_PROVIDER = "telegram"


@dataclass
class AuthResult:
    user: User
    access_token: str
    expires_at: object
    is_new_user: bool


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def authenticate_telegram(self, init_data: str) -> AuthResult:
        """The signature is checked before a single field of the payload is used."""
        parsed = verify_init_data(
            init_data,
            settings.TELEGRAM_BOT_TOKEN,
            max_age_seconds=settings.TELEGRAM_INIT_DATA_MAX_AGE_SECONDS,
        )
        return await self._login_telegram_user(parsed.user)

    async def authenticate_dev(
        self,
        telegram_id: int,
        *,
        first_name: str = "Dev",
        last_name: str | None = None,
        username: str | None = None,
        language_code: str = "ru",
    ) -> AuthResult:
        """Development only. Refuses to run outside APP_ENV=development/test."""
        if settings.is_production or not settings.is_development:
            raise ForbiddenError("Dev auth is disabled", code="DEV_AUTH_DISABLED")
        user = TelegramUser(
            id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code=language_code,
        )
        return await self._login_telegram_user(user)

    async def _login_telegram_user(self, tg_user: TelegramUser) -> AuthResult:
        provider_user_id = str(tg_user.id)
        identity = await self.users.get_identity(TELEGRAM_PROVIDER, provider_user_id)
        is_new_user = identity is None

        if identity is None:
            user = await self.users.create_user()
            identity = await self.users.add_identity(
                user,
                TELEGRAM_PROVIDER,
                provider_user_id,
                meta={"is_premium": tg_user.is_premium, "username": tg_user.username},
            )
        else:
            user = await self.users.get(identity.user_id)
            if user is None or not user.is_active:
                raise ForbiddenError("Account is disabled", code="ACCOUNT_DISABLED")
            identity.meta = {"is_premium": tg_user.is_premium, "username": tg_user.username}

        await self.users.upsert_profile(
            user.id,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            username=tg_user.username,
            avatar_url=tg_user.photo_url,
            language_code=tg_user.language_code,
        )
        await self.users.upsert_preferences(user.id, language=tg_user.language_code)

        token, expires_at = create_access_token(user.id)
        return AuthResult(
            user=user, access_token=token, expires_at=expires_at, is_new_user=is_new_user
        )
