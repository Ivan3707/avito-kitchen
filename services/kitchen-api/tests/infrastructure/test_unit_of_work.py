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
