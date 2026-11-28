import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.catalog_state import CatalogState

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class CatalogStateDatabase:
    session_factory: async_sessionmaker[AsyncSession]
    fixture_initial_revision: int


@pytest_asyncio.fixture(scope="session")
async def catalog_state_database() -> AsyncIterator[CatalogStateDatabase]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for catalog state DB tests")
    url = make_url(database_url)
    if url.host not in {"localhost", "127.0.0.1"} or (
        url.database is None or "test" not in url.database
    ):
        raise RuntimeError(
            "TEST_DATABASE_URL must target a localhost disposable test database"
        )

    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        await session.execute(update(CatalogState).values(catalog_revision=0))
        await session.commit()
        initial_revision = await session.scalar(
            select(CatalogState.catalog_revision).where(CatalogState.id == 1)
        )
    if initial_revision is None:
        raise RuntimeError("catalog state row is missing after migration")

    yield CatalogStateDatabase(
        session_factory=session_factory,
        fixture_initial_revision=initial_revision,
    )
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def reset_catalog_revision(
    catalog_state_database: CatalogStateDatabase,
) -> None:
    async with catalog_state_database.session_factory() as session:
        await session.execute(update(CatalogState).values(catalog_revision=0))
        await session.commit()


async def get_revision(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with UnitOfWork(session_factory) as uow:
        state = await uow.catalog.catalog_state.get_current()
        return state.catalog_revision


@pytest.mark.asyncio
async def test_initial_catalog_revision_is_zero(
    catalog_state_database: CatalogStateDatabase,
) -> None:
    assert catalog_state_database.fixture_initial_revision == 0
    assert await get_revision(catalog_state_database.session_factory) == 0


@pytest.mark.asyncio
async def test_increment_is_persisted_on_commit(
    catalog_state_database: CatalogStateDatabase,
) -> None:
    session_factory = catalog_state_database.session_factory
    async with UnitOfWork(session_factory) as uow:
        assert await uow.catalog.catalog_state.increment() == 1

    assert await get_revision(session_factory) == 1


@pytest.mark.asyncio
async def test_increment_is_discarded_on_rollback(
    catalog_state_database: CatalogStateDatabase,
) -> None:
    session_factory = catalog_state_database.session_factory
    with pytest.raises(RuntimeError, match="rollback requested"):
        async with UnitOfWork(session_factory) as uow:
            await uow.catalog.catalog_state.increment()
            raise RuntimeError("rollback requested")

    assert await get_revision(session_factory) == 0


@pytest.mark.asyncio
async def test_two_sequential_increments(
    catalog_state_database: CatalogStateDatabase,
) -> None:
    session_factory = catalog_state_database.session_factory
    async with UnitOfWork(session_factory) as uow:
        assert await uow.catalog.catalog_state.increment() == 1
        assert await uow.catalog.catalog_state.increment() == 2

    assert await get_revision(session_factory) == 2


@pytest.mark.asyncio
async def test_concurrent_increments_do_not_lose_updates(
    catalog_state_database: CatalogStateDatabase,
) -> None:
    session_factory = catalog_state_database.session_factory
    first_has_lock = asyncio.Event()
    release_first = asyncio.Event()

    async def first_increment() -> int:
        async with UnitOfWork(session_factory) as uow:
            revision = await uow.catalog.catalog_state.increment()
            first_has_lock.set()
            await release_first.wait()
            return revision

    async def second_increment() -> int:
        await first_has_lock.wait()
        async with UnitOfWork(session_factory) as uow:
            return await uow.catalog.catalog_state.increment()

    first_task = asyncio.create_task(first_increment())
    await asyncio.wait_for(first_has_lock.wait(), timeout=2)
    second_task = asyncio.create_task(second_increment())
    try:
        await asyncio.sleep(0.1)
        assert second_task.done() is False
    finally:
        release_first.set()

    assert await first_task == 1
    assert await second_task == 2
    assert await get_revision(session_factory) == 2
