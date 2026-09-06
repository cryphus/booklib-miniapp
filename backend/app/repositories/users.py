from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserIdentity, UserPreferences, UserProfile


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_identity(self, provider: str, provider_user_id: str) -> User | None:
        stmt = (
            select(User)
            .join(UserIdentity, UserIdentity.user_id == User.id)
            .where(
                UserIdentity.provider == provider,
                UserIdentity.provider_user_id == provider_user_id,
            )
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_identity(self, provider: str, provider_user_id: str) -> UserIdentity | None:
        stmt = select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_user_id == provider_user_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def create_user(self) -> User:
        user = User(is_active=True, onboarding_completed=False)
        self.session.add(user)
        await self.session.flush()
        return user

    async def add_identity(
        self, user: User, provider: str, provider_user_id: str, meta: dict | None = None
    ) -> UserIdentity:
        identity = UserIdentity(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            meta=meta,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(identity)
        await self.session.flush()
        return identity

    async def get_profile(self, user_id: uuid.UUID) -> UserProfile | None:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def upsert_profile(self, user_id: uuid.UUID, **fields) -> UserProfile:
        profile = await self.get_profile(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id, **fields)
            self.session.add(profile)
        else:
            for key, value in fields.items():
                if value is not None:
                    setattr(profile, key, value)
        await self.session.flush()
        return profile

    async def get_preferences(self, user_id: uuid.UUID) -> UserPreferences | None:
        stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def upsert_preferences(self, user_id: uuid.UUID, **fields) -> UserPreferences:
        prefs = await self.get_preferences(user_id)
        if prefs is None:
            prefs = UserPreferences(user_id=user_id, **{k: v for k, v in fields.items() if v is not None})
            self.session.add(prefs)
        else:
            for key, value in fields.items():
                if value is not None:
                    setattr(prefs, key, value)
        await self.session.flush()
        return prefs
