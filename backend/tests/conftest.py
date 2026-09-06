from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-BOT-TOKEN")
os.environ.setdefault("AI_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_DIM", "64")
# The relevance floor is calibrated for a real embedding model. FakeEmbeddingProvider is a
# hashed bag-of-words, whose cosine scores sit on a different scale, so tests lower it.
os.environ.setdefault("AI_MIN_RELEVANCE", "0.05")
os.environ.setdefault("FREE_AI_REQUESTS_PER_MONTH", "3")
os.environ.setdefault("PREMIUM_AI_REQUESTS_PER_MONTH", "100")
os.environ.setdefault("STORAGE_LOCAL_DIR", tempfile.mkdtemp(prefix="remarka-uploads-"))
os.environ.setdefault("RATE_LIMIT_ENABLED", "False")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.deps import get_current_user  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.db.sqlite_compat import install_sqlite_unicode_functions  # noqa: E402
from app.integrations.ai import (  # noqa: E402
    FakeEmbeddingProvider,
    FakeLLMProvider,
    reset_providers,
    set_providers,
)
from app.integrations.payments.factory import PaymentProviderFactory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.billing_service import BillingService  # noqa: E402


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    install_sqlite_unicode_functions(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
        await session.commit()


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider(dimensions=64)


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
async def app(session_factory, fake_embeddings, fake_llm):
    set_providers(embedding=fake_embeddings, llm=fake_llm)
    application = create_app()

    async def override_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_session] = override_session
    yield application
    application.dependency_overrides.clear()
    reset_providers()
    PaymentProviderFactory.reset_overrides()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _login(client: AsyncClient, telegram_id: int, name: str = "User") -> str:
    response = await client.post(
        "/api/v1/auth/dev", json={"telegram_id": telegram_id, "first_name": name}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def user_a(client) -> dict:
    token = await _login(client, 100001, "Alice")
    return {"headers": {"Authorization": f"Bearer {token}"}, "token": token}


@pytest.fixture
async def user_b(client) -> dict:
    token = await _login(client, 100002, "Bob")
    return {"headers": {"Authorization": f"Bearer {token}"}, "token": token}


@pytest.fixture
async def plans(session):
    await BillingService(session).ensure_plans()
    await session.commit()


async def add_book(client: AsyncClient, headers: dict, title: str = "Test Book", **kwargs) -> dict:
    payload = {
        "title": title,
        "authors": kwargs.pop("authors", ["Test Author"]),
        **kwargs,
    }
    response = await client.post("/api/v1/books/manual", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def add_entry(
    client: AsyncClient, headers: dict, user_book_id: str, **kwargs
) -> dict:
    payload = {
        "type": kwargs.pop("type", "quote"),
        "content": kwargs.pop("content", "Test content"),
        **kwargs,
    }
    response = await client.post(
        f"/api/v1/library/{user_book_id}/entries", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


__all__ = ["add_book", "add_entry", "get_current_user"]
