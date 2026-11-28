from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.orders.models.order import Order
from app.modules.users.models.user import User

pytestmark = pytest.mark.integration


async def create_order_dependencies(uow: UnitOfWork):
    user = User(
        email=f"user-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    uow.users.users.add(user)

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

    await uow.session.flush()

    return user, restaurant, branch


@pytest.mark.asyncio
async def test_add_and_get_by_id(uow: UnitOfWork):
    user, restaurant, branch = await create_order_dependencies(uow)

    order = Order(
        user_id=user.id,
        restaurant_id=restaurant.id,
        branch_id=branch.id,
        external_order_id=f"external-{uuid4()}",
        restaurant_order_id=f"restaurant-order-{uuid4()}",
        request_hash=f"hash-{uuid4()}",
        status="confirmed",
    )

    uow.orders.orders.add(order)

    await uow.session.commit()

    saved_order = await uow.orders.orders.get_by_id(order.id)

    assert saved_order is not None
    assert saved_order.id == order.id
    assert saved_order.user_id == user.id
    assert saved_order.restaurant_id == restaurant.id
    assert saved_order.branch_id == branch.id
    assert saved_order.external_order_id == order.external_order_id
    assert saved_order.restaurant_order_id == order.restaurant_order_id
    assert saved_order.request_hash == order.request_hash


@pytest.mark.asyncio
async def test_get_by_external_id(uow: UnitOfWork):
    user, restaurant, branch = await create_order_dependencies(uow)

    external_order_id = f"external-{uuid4()}"

    order = Order(
        user_id=user.id,
        restaurant_id=restaurant.id,
        branch_id=branch.id,
        external_order_id=external_order_id,
        restaurant_order_id=f"restaurant-order-{uuid4()}",
        request_hash=f"hash-{uuid4()}",
        status="confirmed",
    )

    uow.orders.orders.add(order)

    await uow.session.commit()

    saved_order = await uow.orders.orders.get_by_external_id(
        restaurant_id=restaurant.id,
        external_order_id=external_order_id,
    )

    assert saved_order is not None
    assert saved_order.id == order.id
    assert saved_order.restaurant_id == restaurant.id
    assert saved_order.external_order_id == external_order_id


@pytest.mark.asyncio
async def test_get_by_external_id_returns_none(
    uow: UnitOfWork,
):
    _, restaurant, _ = await create_order_dependencies(uow)

    order = await uow.orders.orders.get_by_external_id(
        restaurant_id=restaurant.id,
        external_order_id="non-existent-order",
    )

    assert order is None


@pytest.mark.asyncio
async def test_get_by_restaurant_order_id(
    uow: UnitOfWork,
):
    user, restaurant, branch = await create_order_dependencies(uow)

    restaurant_order_id = f"restaurant-order-{uuid4()}"

    order = Order(
        user_id=user.id,
        restaurant_id=restaurant.id,
        branch_id=branch.id,
        external_order_id=f"external-{uuid4()}",
        restaurant_order_id=restaurant_order_id,
        request_hash=f"hash-{uuid4()}",
        status="confirmed",
    )

    uow.orders.orders.add(order)

    await uow.session.commit()

    saved_order = await uow.orders.orders.get_by_restaurant_order_id(
        restaurant_id=restaurant.id,
        restaurant_order_id=restaurant_order_id,
    )

    assert saved_order is not None
    assert saved_order.id == order.id
    assert saved_order.restaurant_id == restaurant.id
    assert saved_order.restaurant_order_id == restaurant_order_id
