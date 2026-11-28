from collections.abc import AsyncIterator

import pytest_asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base
from app.infrastructure.unit_of_work import UnitOfWork


class TestSettings(BaseSettings):
    test_database_url: str

    model_config = SettingsConfigDict(
        env_file=".env.test",
        env_file_encoding="utf-8",
        extra="ignore",
    )


test_settings = TestSettings()


def _assert_disposable_database() -> None:
    url = make_url(test_settings.test_database_url)
    if url.host not in {"localhost", "127.0.0.1"} or (
        url.database is None or "test" not in url.database
    ):
        raise RuntimeError(
            "TEST_DATABASE_URL must target a localhost disposable test database"
        )


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    _assert_disposable_database()
    engine = create_async_engine(
        test_settings.test_database_url,
        poolclass=NullPool,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def uow(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(test_session_factory) as unit_of_work:
        yield unit_of_work
