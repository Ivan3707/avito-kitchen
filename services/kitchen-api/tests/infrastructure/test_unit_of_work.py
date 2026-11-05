
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

import pytest

from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.unit_of_work import UnitOfWork



@pytest.mark.asyncio
async def test_unit_of_work_uses_same_session_for_repository(
    test_session_factory,
):
    async with UnitOfWork(test_session_factory) as uow:
        assert uow.restaurants.session is uow.session


@pytest.mark.asyncio
async def test_unit_of_work_commits_on_success(
    test_session_factory,
):
    external_id = f"test-{uuid4()}"

    restaurant = Restaurant(
        external_id=external_id,
        name="Test Restaurant",
    )

    async with UnitOfWork(test_session_factory) as uow:
        uow.restaurants.add(restaurant)

    async with UnitOfWork(test_session_factory) as uow:
        saved_restaurant = await uow.restaurants.get_by_external_id(
            external_id
        )

        assert saved_restaurant is not None
        assert saved_restaurant.external_id == external_id
        assert saved_restaurant.name == "Test Restaurant"


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_on_exception(
    test_session_factory,
):
    external_id = f"test-{uuid4()}"

    restaurant = Restaurant(
        external_id=external_id,
        name="Should Not Exist",
    )

    with pytest.raises(RuntimeError):
        async with UnitOfWork(test_session_factory) as uow:
            uow.restaurants.add(restaurant)

            raise RuntimeError("test rollback")

    async with UnitOfWork(test_session_factory) as uow:
        saved_restaurant = await uow.restaurants.get_by_external_id(
            external_id
        )

        assert saved_restaurant is None

@pytest.mark.asyncio
async def test_unit_of_work_preserves_original_error_on_rollback_failure():
    session = AsyncMock(spec=AsyncSession)
    rollback_error = RuntimeError("rollback failed")
    original_error = ValueError("business operation failed")
    session.rollback.side_effect = rollback_error

    uow = UnitOfWork(lambda: session)

    with pytest.raises(ValueError, match="business operation failed") as exc_info:
        async with uow:
            raise original_error

    assert exc_info.value is original_error
    assert any(
        "rollback failed" in note
        for note in exc_info.value.__notes__
    )
    session.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_unit_of_work_preserves_commit_error_on_close_failure():
    session = AsyncMock(spec=AsyncSession)
    commit_error = RuntimeError("commit failed")
    session.commit.side_effect = commit_error
    session.close.side_effect = OSError("close failed")

    uow = UnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="commit failed") as exc_info:
        async with uow:
            pass

    assert exc_info.value is commit_error
    assert any(
        "close failed" in note
        for note in exc_info.value.__notes__
    )
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_unit_of_work_raises_close_error_when_commit_succeeds():
    session = AsyncMock(spec=AsyncSession)
    close_error = OSError("close failed")
    session.close.side_effect = close_error

    uow = UnitOfWork(lambda: session)

    with pytest.raises(OSError, match="close failed") as exc_info:
        async with uow:
            pass

    assert exc_info.value is close_error