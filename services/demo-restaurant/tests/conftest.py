import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.infrastructure.database import models  # noqa: F401


def _test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is required for catalog DB tests")
    url = make_url(value)
    if url.host not in {"localhost", "127.0.0.1"} or (
        url.database is None or "test" not in url.database
    ):
        raise RuntimeError(
            "TEST_DATABASE_URL must target a localhost disposable test database"
        )
    return value


@pytest_asyncio.fixture(scope="session")
async def demo_session_factory() -> AsyncIterator[
    async_sessionmaker[AsyncSession]
]:
    engine = create_async_engine(_test_database_url(), poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def clean_catalog_database(
    demo_session_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    async with demo_session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE branch_menu_items, restaurant_order_items, "
                "restaurant_orders, menu_items, restaurant_branches CASCADE"
            )
        )
        await session.execute(
            text(
                "UPDATE catalog_state SET catalog_revision = 0, "
                "restaurant_name = 'Demo Restaurant', "
                "restaurant_description = NULL, menu_name = 'Menu' "
                "WHERE id = 1"
            )
        )
        await session.commit()
    return demo_session_factory
