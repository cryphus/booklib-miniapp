from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import GUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Some backends (SQLite in tests) return naive datetimes; treat those as UTC."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
