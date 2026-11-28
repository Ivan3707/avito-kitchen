from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.restaurant import (
    Restaurant,
)
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_add_and_get_by_id(
    uow: UnitOfWork,
):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.catalog.restaurants.add(restaurant)

    await uow.session.flush()

    branch = RestaurantBranch(
        restaurant_id=restaurant.id,
        external_id=f"branch-{uuid4()}",
        name="Test Branch",
        address="Test Address",
    )

    uow.catalog.restaurant_branches.add(branch)

    await uow.session.commit()

    saved_branch = await uow.catalog.restaurant_branches.get_by_id(branch.id)

    assert saved_branch is not None
    assert saved_branch.id == branch.id
    assert saved_branch.restaurant_id == restaurant.id


@pytest.mark.asyncio
async def test_get_by_restaurant_and_external_id(
    uow: UnitOfWork,
):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.catalog.restaurants.add(restaurant)

    await uow.session.flush()

    external_id = f"branch-{uuid4()}"

    branch = RestaurantBranch(
        restaurant_id=restaurant.id,
        external_id=external_id,
        name="Test Branch",
        address="Test Address",
    )

    uow.catalog.restaurant_branches.add(branch)

    await uow.session.commit()

    saved_branch = await (
        uow.catalog.restaurant_branches.get_by_restaurant_and_external_id(
            restaurant_id=restaurant.id,
            external_id=external_id,
        )
    )

    assert saved_branch is not None
    assert saved_branch.id == branch.id
    assert saved_branch.restaurant_id == restaurant.id
    assert saved_branch.external_id == external_id


@pytest.mark.asyncio
async def test_get_by_restaurant_and_external_id_returns_none(
    uow: UnitOfWork,
):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.catalog.restaurants.add(restaurant)

    await uow.session.commit()

    branch = await uow.catalog.restaurant_branches.get_by_restaurant_and_external_id(
        restaurant_id=restaurant.id,
        external_id=f"missing-{uuid4()}",
    )

    assert branch is None
