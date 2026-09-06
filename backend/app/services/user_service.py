from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import logger
from app.models import (
    AIConversation,
    Book,
    Category,
    Entry,
    EntryEmbedding,
    EntryType,
    Subscription,
    SubscriptionStatus,
    Tag,
    User,
    UserBook,
    UserIdentity,
)
from app.repositories import BookRepository, TagRepository, UserRepository
from app.schemas.user import (
    AIUsageOut,
    MeOut,
    PreferencesOut,
    PreferencesUpdate,
    ProfileOut,
    StatsOut,
)
from app.services.billing_service import BillingService
from app.services.storage import get_storage


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.books = BookRepository(session)
        self.tags = TagRepository(session)
        self.billing = BillingService(session)

    async def get_me(self, user: User) -> MeOut:
        profile = await self.users.get_profile(user.id)
        preferences = await self.users.get_preferences(user.id)
        quota = await self.billing.get_ai_quota(user.id)
        return MeOut(
            id=user.id,
            created_at=user.created_at,
            onboarding_completed=user.onboarding_completed,
            profile=ProfileOut.model_validate(profile) if profile else ProfileOut(),
            preferences=(
                PreferencesOut.model_validate(preferences) if preferences else PreferencesOut()
            ),
            plan=quota.plan,
            is_premium=quota.plan == "premium",
            ai_usage=AIUsageOut(
                plan=quota.plan,
                used=quota.used,
                limit=quota.limit,
                remaining=quota.remaining,
                period_end=quota.period_end,
            ),
        )

    async def update_me(self, user: User, *, onboarding_completed: bool | None = None) -> MeOut:
        if onboarding_completed is not None:
            user.onboarding_completed = onboarding_completed
        await self.session.flush()
        return await self.get_me(user)

    async def get_preferences(self, user_id: uuid.UUID) -> PreferencesOut:
        preferences = await self.users.get_preferences(user_id)
        return PreferencesOut.model_validate(preferences) if preferences else PreferencesOut()

    async def update_preferences(
        self, user_id: uuid.UUID, payload: PreferencesUpdate
    ) -> PreferencesOut:
        preferences = await self.users.upsert_preferences(
            user_id, theme=payload.theme, language=payload.language
        )
        return PreferencesOut.model_validate(preferences)

    async def stats(self, user_id: uuid.UUID) -> StatsOut:
        books_count = (
            await self.session.execute(
                select(func.count()).select_from(UserBook).where(UserBook.user_id == user_id)
            )
        ).scalar_one()

        type_counts = dict(
            (
                await self.session.execute(
                    select(Entry.type, func.count())
                    .where(Entry.user_id == user_id)
                    .group_by(Entry.type)
                )
            ).all()
        )
        quotes = type_counts.get(EntryType.quote, 0)
        notes = type_counts.get(EntryType.note, 0)

        favorite_entries = (
            await self.session.execute(
                select(func.count())
                .select_from(Entry)
                .where(Entry.user_id == user_id, Entry.is_favorite.is_(True))
            )
        ).scalar_one()
        favorite_books = (
            await self.session.execute(
                select(func.count())
                .select_from(UserBook)
                .where(UserBook.user_id == user_id, UserBook.is_favorite.is_(True))
            )
        ).scalar_one()

        return StatsOut(
            books_count=books_count,
            quotes_count=quotes,
            notes_count=notes,
            entries_count=quotes + notes,
            favorites_count=favorite_entries + favorite_books,
            tags_count=await self.tags.count_for_user(user_id),
        )

    async def delete_account(self, user: User) -> None:
        """Deletes every trace of one user in a single transaction.

        Global catalog rows survive: a book another reader has in their library is never
        removed, and covers uploaded for a shared book are kept.
        """
        user_id = user.id
        storage = get_storage()

        # 1. uploaded covers for books nobody else uses
        rows = (
            await self.session.execute(
                select(Book.id, Book.cover_url).where(Book.created_by_user_id == user_id)
            )
        ).all()
        for book_id, cover_url in rows:
            if not cover_url or not cover_url.startswith(storage.url_for("")):
                continue
            if await self.books.book_used_by_others(book_id, user_id):
                continue
            key = cover_url.replace(storage.url_for(""), "")
            try:
                await storage.delete(key)
            except OSError as exc:
                logger.warning("cover_delete_failed err=%s", type(exc).__name__)

        # 2. detach the user's authorship from shared catalog rows
        for book in (
            (await self.session.execute(select(Book).where(Book.created_by_user_id == user_id)))
            .scalars()
            .all()
        ):
            book.created_by_user_id = None

        # 3. cancel active subscriptions, keep payment records for accounting
        for subscription in (
            (
                await self.session.execute(
                    select(Subscription).where(
                        Subscription.user_id == user_id,
                        Subscription.status == SubscriptionStatus.active,
                    )
                )
            )
            .scalars()
            .all()
        ):
            subscription.status = SubscriptionStatus.canceled

        # 4. user-owned data. FK cascades handle entry_tags / ai_messages / ai_message_sources.
        await self.session.execute(
            delete(EntryEmbedding).where(EntryEmbedding.user_id == user_id)
        )
        await self.session.execute(delete(Entry).where(Entry.user_id == user_id))
        await self.session.execute(delete(AIConversation).where(AIConversation.user_id == user_id))
        await self.session.execute(delete(UserBook).where(UserBook.user_id == user_id))
        await self.session.execute(delete(Tag).where(Tag.user_id == user_id))
        await self.session.execute(delete(Category).where(Category.user_id == user_id))
        await self.session.execute(delete(UserIdentity).where(UserIdentity.user_id == user_id))
        # The bulk delete bypasses the ORM, so drop the stale loaded collection before
        # deleting the user or the cascade would try to delete those rows again.
        self.session.expire(user, ["identities"])

        # 5. finally the account itself (profile/preferences cascade from users)
        await self.session.delete(user)
        await self.session.flush()

    async def require_user(self, user_id: uuid.UUID) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")
        return user
