"""Development seed data.

Run manually only:  python -m app.seed
Refuses to run when APP_ENV=production.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.models import Book, EntryType
from app.repositories import BookRepository, EntryRepository, TagRepository, UserRepository
from app.services.billing_service import BillingService
from app.services.indexing_service import IndexingService

DEV_TELEGRAM_ID = "100500"

BOOKS: list[dict] = [
    {
        "title": "Психология денег",
        "authors": ["Морган Хаузел"],
        "category": "Финансы",
        "isbn_13": "9785001955948",
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780857197689-L.jpg",
        "published_year": 2020,
        "entries": [
            {
                "type": "quote",
                "content": (
                    "Богатство — это то, чего вы не видите. Это машины, которые не были куплены, "
                    "и вещи, от которых отказались."
                ),
                "personal_note": "Отличная мысль про разницу между богатством и роскошью.",
                "chapter": "5",
                "page": "84",
                "tags": ["деньги", "богатство"],
                "is_favorite": True,
            },
            {
                "type": "quote",
                "content": (
                    "Управление капиталом важнее доходности инвестиций: сохранить деньги сложнее, "
                    "чем их заработать."
                ),
                "chapter": "4",
                "tags": ["деньги", "инвестиции", "долгосрочность"],
            },
            {
                "type": "note",
                "content": (
                    "Моя мысль: главный риск для сбережений — не рынок, а собственные решения "
                    "в момент паники."
                ),
                "tags": ["деньги", "психология"],
            },
        ],
    },
    {
        "title": "Атомные привычки",
        "authors": ["Джеймс Клир"],
        "category": "Саморазвитие",
        "isbn_13": "9785041101718",
        "published_year": 2018,
        "entries": [
            {
                "type": "quote",
                "content": (
                    "Вы не достигаете уровня своих целей, вы падаете до уровня своих систем."
                ),
                "chapter": "1",
                "tags": ["привычки", "системы"],
                "is_favorite": True,
            },
            {
                "type": "note",
                "content": "Попробовать правило двух минут для утренней рутины.",
                "tags": ["привычки"],
            },
        ],
    },
    {
        "title": "Самый богатый человек в Вавилоне",
        "authors": ["Джордж Клейсон"],
        "category": "Финансы",
        "published_year": 1926,
        "entries": [
            {
                "type": "quote",
                "content": "Часть всего заработанного тобой — твоя, и ты должен оставлять её себе.",
                "tags": ["деньги", "сбережения"],
            }
        ],
    },
    {
        "title": "Думай и богатей",
        "authors": ["Наполеон Хилл"],
        "category": "Саморазвитие",
        "published_year": 1937,
        "entries": [
            {
                "type": "note",
                "content": "Многое из книги устарело, но идея про конкретную цель работает.",
                "tags": ["цели"],
            }
        ],
    },
    {
        "title": "1984",
        "authors": ["Джордж Оруэлл"],
        "category": "Художественная",
        "published_year": 1949,
        "entries": [
            {
                "type": "quote",
                "content": "Свобода — это возможность сказать, что дважды два четыре.",
                "chapter": "7",
                "tags": ["свобода"],
                "is_favorite": True,
            }
        ],
    },
    {
        "title": "Мастер и Маргарита",
        "authors": ["Михаил Булгаков"],
        "category": "Художественная",
        "published_year": 1967,
        "entries": [
            {
                "type": "quote",
                "content": "Никогда и ничего не просите! Сами предложат и сами всё дадут.",
                "chapter": "24",
                "tags": ["жизнь"],
            }
        ],
    },
]


async def seed() -> None:
    if settings.is_production:
        raise SystemExit("Seeding is disabled in production")

    async with SessionLocal() as session:
        users = UserRepository(session)
        books = BookRepository(session)
        entries = EntryRepository(session)
        tags = TagRepository(session)
        indexing = IndexingService(session)

        await BillingService(session).ensure_plans()

        user = await users.get_by_identity("telegram", DEV_TELEGRAM_ID)
        if user is None:
            user = await users.create_user()
            await users.add_identity(user, "telegram", DEV_TELEGRAM_ID, meta={"seed": True})
            await users.upsert_profile(
                user.id, first_name="Dev", username="dev_reader", language_code="ru"
            )
            await users.upsert_preferences(user.id, theme="system", language="ru")
            logger.info("seed_user_created id=%s", user.id)

        created_books = 0
        created_entries = 0

        for spec in BOOKS:
            # Seed books without an ISBN cannot be deduplicated by identifier, so fall
            # back to an exact title match to keep repeated runs idempotent.
            book = await books.find_duplicate(isbn_13=spec.get("isbn_13"))
            if book is None:
                book = (
                    await session.execute(
                        select(Book).where(Book.title == spec["title"], Book.source == "seed")
                    )
                ).scalars().first()
            if book is None:
                book = await books.create_book(
                    title=spec["title"],
                    authors=spec["authors"],
                    isbn_13=spec.get("isbn_13"),
                    published_year=spec.get("published_year"),
                    cover_url=spec.get("cover_url"),
                    source="seed",
                    created_by_user_id=user.id,
                )
            user_book = await books.get_user_book_by_book(user.id, book.id)
            if user_book is None:
                category = await books.get_or_create_category(user.id, spec["category"])
                user_book = await books.add_to_library(
                    user.id, book.id, category.id if category else None
                )
                created_books += 1

            existing, _total = await entries.list_for_book(user.id, user_book.id, limit=100)
            existing_content = {e.content for e in existing}

            for entry_spec in spec["entries"]:
                if entry_spec["content"] in existing_content:
                    continue
                entry = await entries.create(
                    user_id=user.id,
                    user_book_id=user_book.id,
                    type=EntryType(entry_spec["type"]),
                    content=entry_spec["content"],
                    personal_note=entry_spec.get("personal_note"),
                    chapter=entry_spec.get("chapter"),
                    page=entry_spec.get("page"),
                    is_favorite=entry_spec.get("is_favorite", False),
                )
                if entry_spec.get("tags"):
                    await tags.set_entry_tags(entry, entry_spec["tags"])
                await session.flush()
                await indexing.index_entry(entry)
                created_entries += 1

        await session.commit()
        logger.info(
            "seed_done books=%s entries=%s telegram_id=%s",
            created_books,
            created_entries,
            DEV_TELEGRAM_ID,
        )
        print(
            f"Seeded {created_books} books and {created_entries} entries.\n"
            f"Log in with POST /api/v1/auth/dev  {{'telegram_id': {DEV_TELEGRAM_ID}}}"
        )


if __name__ == "__main__":
    asyncio.run(seed())
