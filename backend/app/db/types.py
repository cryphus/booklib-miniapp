from __future__ import annotations

import json
import uuid

from sqlalchemy import CHAR, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from app.core.config import settings


class GUID(TypeDecorator):
    """UUID on PostgreSQL, 36-char string elsewhere (so the test suite can run on SQLite)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class JSONBType(TypeDecorator):
    """JSONB on PostgreSQL, JSON-encoded text elsewhere."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value if dialect.name == "postgresql" else json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.loads(value)


class EmbeddingVector(TypeDecorator):
    """pgvector column on PostgreSQL; JSON list fallback for SQLite-backed tests."""

    impl = Text
    cache_ok = True

    def __init__(self, dim: int | None = None) -> None:
        super().__init__()
        self.dim = dim or settings.EMBEDDING_DIM

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return json.dumps(list(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        return json.loads(value)
