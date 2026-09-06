"""SQLite compatibility shims.

PostgreSQL is the production database. SQLite is used by the test suite, and its built-in
``lower()``/``upper()`` only fold ASCII, so ILIKE against Cyrillic text would silently miss
matches there. Registering Python's Unicode-aware versions makes search behave the same on
both backends.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine


def _register(dbapi_connection, _connection_record) -> None:
    create_function = getattr(dbapi_connection, "create_function", None)
    if create_function is None:  # aiosqlite wraps the driver connection
        driver = getattr(dbapi_connection, "_connection", None)
        create_function = getattr(driver, "create_function", None)
    if create_function is None:
        return
    create_function("lower", 1, lambda value: value.lower() if isinstance(value, str) else value)
    create_function("upper", 1, lambda value: value.upper() if isinstance(value, str) else value)


def install_sqlite_unicode_functions(engine: Engine | AsyncEngine) -> None:
    target = engine.sync_engine if isinstance(engine, AsyncEngine) else engine
    if target.dialect.name != "sqlite":
        return
    event.listen(target, "connect", _register)
