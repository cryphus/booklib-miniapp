"""Initial Remarka schema.

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.config import settings
from app.db.types import GUID, EmbeddingVector, JSONBType

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    timestamps = [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]

    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps,
    )

    op.create_table(
        "user_identities",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("metadata", JSONBType(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_identity_provider_user"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
    op.create_index("ix_user_identities_provider_user_id", "user_identities", ["provider_user_id"])

    op.create_table(
        "user_profiles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(128), nullable=True),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("language_code", sa.String(16), nullable=True),
        *timestamps,
        sa.UniqueConstraint("user_id", name="uq_profile_user"),
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("theme", sa.String(16), nullable=False, server_default="system"),
        sa.Column("language", sa.String(16), nullable=True),
        *timestamps,
        sa.UniqueConstraint("user_id", name="uq_preferences_user"),
    )

    # ---------- catalog ----------
    op.create_table(
        "books",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("subtitle", sa.String(512), nullable=True),
        sa.Column("authors", JSONBType(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("isbn_10", sa.String(16), nullable=True),
        sa.Column("isbn_13", sa.String(20), nullable=True),
        sa.Column("published_year", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(256), nullable=True),
        sa.Column("cover_url", sa.String(1024), nullable=True),
        sa.Column("google_books_id", sa.String(64), nullable=True),
        sa.Column("open_library_id", sa.String(64), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("metadata", JSONBType(), nullable=True),
        sa.Column(
            "created_by_user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *timestamps,
    )
    op.create_index("ix_books_isbn_13", "books", ["isbn_13"])
    op.create_index("ix_books_isbn_10", "books", ["isbn_10"])
    op.create_index("ix_books_google_books_id", "books", ["google_books_id"])
    op.create_index("ix_books_open_library_id", "books", ["open_library_id"])
    op.create_index("ix_books_title", "books", ["title"])

    op.create_table(
        "categories",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("normalized_name", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_category_user_name"),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])

    op.create_table(
        "user_books",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", GUID(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "category_id",
            GUID(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps,
        sa.UniqueConstraint("user_id", "book_id", name="uq_user_book"),
    )
    op.create_index("ix_user_books_user_id", "user_books", ["user_id"])
    op.create_index("ix_user_books_book_id", "user_books", ["book_id"])
    op.create_index("ix_user_books_created_at", "user_books", ["created_at"])
    op.create_index("ix_user_books_user_favorite", "user_books", ["user_id", "is_favorite"])

    # ---------- entries ----------
    op.create_table(
        "entries",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "user_book_id",
            GUID(),
            sa.ForeignKey("user_books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum("quote", "note", name="entry_type", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("personal_note", sa.Text(), nullable=True),
        sa.Column("chapter", sa.String(128), nullable=True),
        sa.Column("page", sa.String(32), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps,
    )
    op.create_index("ix_entries_user_id", "entries", ["user_id"])
    op.create_index("ix_entries_user_book_id", "entries", ["user_book_id"])
    op.create_index("ix_entries_created_at", "entries", ["created_at"])
    op.create_index("ix_entries_user_type", "entries", ["user_id", "type"])
    op.create_index("ix_entries_user_favorite", "entries", ["user_id", "is_favorite"])

    op.create_table(
        "tags",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("normalized_name", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_tag_user_normalized"),
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"])

    op.create_table(
        "entry_tags",
        sa.Column(
            "entry_id", GUID(), sa.ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("tag_id", GUID(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "entry_embeddings",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "entry_id", GUID(), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("document", sa.Text(), nullable=False),
        sa.Column("embedding", EmbeddingVector(settings.EMBEDDING_DIM), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("entry_id", name="uq_entry_embedding_entry"),
    )
    op.create_index("ix_entry_embeddings_user_id", "entry_embeddings", ["user_id"])

    # ---------- AI ----------
    op.create_table(
        "ai_conversations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "context_type",
            sa.Enum(
                "all_library",
                "current_book",
                "favorites",
                name="ai_context_type",
                native_enum=False,
                length=32,
            ),
            nullable=False,
            server_default="all_library",
        ),
        sa.Column(
            "context_user_book_id",
            GUID(),
            sa.ForeignKey("user_books.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *timestamps,
    )
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_index("ix_ai_conversations_updated_at", "ai_conversations", ["updated_at"])

    op.create_table(
        "ai_messages",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "conversation_id",
            GUID(),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", name="ai_message_role", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])

    op.create_table(
        "ai_message_sources",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "message_id",
            GUID(),
            sa.ForeignKey("ai_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entry_id", GUID(), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("relevance_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_ai_message_sources_message_id", "ai_message_sources", ["message_id"])

    op.create_table(
        "ai_usage",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "period_start", name="uq_ai_usage_user_period"),
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])

    # ---------- billing ----------
    op.create_table(
        "plans",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("ai_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps,
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", GUID(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "expired",
                "canceled",
                "pending",
                name="subscription_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps,
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"])

    op.create_table(
        "payments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_payment_id", sa.String(255), nullable=True),
        sa.Column("payload", sa.String(128), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "succeeded",
                "failed",
                "canceled",
                name="payment_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("metadata", JSONBType(), nullable=True),
        *timestamps,
        sa.UniqueConstraint("provider", "external_payment_id", name="uq_payment_provider_external"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])

    # ---------- Postgres-only search and vector indexes ----------
    if _is_postgres():
        op.execute("CREATE INDEX ix_books_title_trgm ON books USING gin (title gin_trgm_ops)")
        op.execute(
            "CREATE INDEX ix_books_authors_trgm ON books USING gin "
            "((authors::text) gin_trgm_ops)"
        )
        op.execute("CREATE INDEX ix_entries_content_trgm ON entries USING gin (content gin_trgm_ops)")
        op.execute(
            "CREATE INDEX ix_entries_personal_note_trgm ON entries USING gin "
            "(personal_note gin_trgm_ops)"
        )
        op.execute("CREATE INDEX ix_tags_normalized_trgm ON tags USING gin (normalized_name gin_trgm_ops)")
        # IVFFlat needs data to train on; HNSW works on an empty table and is the safer
        # default for a fresh install.
        op.execute(
            "CREATE INDEX ix_entry_embeddings_vector ON entry_embeddings "
            "USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    for table in (
        "payments",
        "subscriptions",
        "plans",
        "ai_usage",
        "ai_message_sources",
        "ai_messages",
        "ai_conversations",
        "entry_embeddings",
        "entry_tags",
        "tags",
        "entries",
        "user_books",
        "categories",
        "books",
        "user_preferences",
        "user_profiles",
        "user_identities",
        "users",
    ):
        op.drop_table(table)
