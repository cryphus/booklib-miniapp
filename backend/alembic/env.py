from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models import Base  # noqa: F401  (imports every model into Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# These are created in the initial migration via raw op.execute(...) — GIN trigram indexes
# and pgvector's HNSW index use operator classes and access methods that a plain
# SQLAlchemy Index() can't express, so there is no ORM-side object to compare them
# against. Without this, `alembic check`/autogenerate sees them in the reflected database,
# finds nothing matching in the models, and proposes to drop them on every run.
POSTGRES_ONLY_INDEXES = {
    "ix_books_title_trgm",
    "ix_books_authors_trgm",
    "ix_entries_content_trgm",
    "ix_entries_personal_note_trgm",
    "ix_tags_normalized_trgm",
    "ix_entry_embeddings_vector",
}


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    if type_ == "index" and name in POSTGRES_ONLY_INDEXES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
