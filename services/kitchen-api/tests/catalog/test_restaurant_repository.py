from uuid import uuid4

import pytest

from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.repositories.restaurant import RestaurantRepository

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_add_and_get_by_id(test_session_factory):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    async with test_session_factory() as session:
        repository = RestaurantRepository(session)

        repository.add(restaurant)

        await session.commit()

        restaurant_id = restaurant.id

    async with test_session_factory() as session:
        repository = RestaurantRepository(session)

        saved_restaurant = await repository.get_by_id(restaurant_id)

        assert saved_restaurant is not None
        assert saved_restaurant.id == restaurant_id
        assert saved_restaurant.name == "Test Restaurant"


@pytest.mark.asyncio
async def test_get_by_external_id_returns_restaurant(
    test_session_factory,
):
    external_id = f"restaurant-{uuid4()}"

    restaurant = Restaurant(
        external_id=external_id,
        name="Test Restaurant",
    )

    async with test_session_factory() as session:
        repository = RestaurantRepository(session)

        repository.add(restaurant)

        await session.commit()

    async with test_session_factory() as session:
        repository = RestaurantRepository(session)

        saved_restaurant = await repository.get_by_external_id(external_id)

        assert saved_restaurant is not None
        assert saved_restaurant.external_id == external_id
        assert saved_restaurant.name == "Test Restaurant"


@pytest.mark.asyncio
async def test_get_by_external_id_returns_none_when_not_found(
    test_session_factory,
):
    external_id = f"non-existent-{uuid4()}"

    async with test_session_factory() as session:
        repository = RestaurantRepository(session)

        saved_restaurant = await repository.get_by_external_id(external_id)

        assert saved_restaurant is None
