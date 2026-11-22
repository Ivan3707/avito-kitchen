from uuid import uuid4

import pytest

from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.order import Order
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.unit_of_work import UnitOfWork


async def create_order_dependencies(uow: UnitOfWork):
    customer = Customer(
        email=f"customer-{uuid4()}@example.com",
    )
    uow.customers.add(customer)

    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )
    uow.restaurants.add(restaurant)

    await uow.session.flush()

    branch = RestaurantBranch(
        restaurant_id=restaurant.id,
        external_id=f"branch-{uuid4()}",
        name="Test Branch",
        address="Test Address",
    )
    uow.restaurant_branches.add(branch)

    await uow.session.flush()

    return customer, restaurant, branch


@pytest.mark.asyncio
async def test_add_and_get_by_id(uow: UnitOfWork):
    customer, restaurant, branch = await create_order_dependencies(uow)

    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        branch_id=branch.id,
        external_order_id=f"external-{uuid4()}",
        restaurant_order_id=f"restaurant-order-{uuid4()}",
        request_hash=f"hash-{uuid4()}",
        status="confirmed",
    )

    uow.orders.add(order)

    await uow.session.commit()

    saved_order = await uow.orders.get_by_id(order.id)

    assert saved_order is not None
    assert saved_order.id == order.id
    assert saved_order.customer_id == customer.id
    assert saved_order.restaurant_id == restaurant.id
    assert saved_order.branch_id == branch.id
    assert saved_order.external_order_id == order.external_order_id
    assert saved_order.restaurant_order_id == order.restaurant_order_id
    assert saved_order.request_hash == order.request_hash


@pytest.mark.asyncio
async def test_get_by_external_id(uow: UnitOfWork):
    customer, restaurant, branch = await create_order_dependencies(uow)

    external_order_id = f"external-{uuid4()}"

    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        branch_id=branch.id,
        external_order_id=external_order_id,
        restaurant_order_id=f"restaurant-order-{uuid4()}",
        request_hash=f"hash-{uuid4()}",
        status="confirmed",
    )

    uow.orders.add(order)

    await uow.session.commit()

    saved_order = await uow.orders.get_by_external_id(
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

    order = await uow.orders.get_by_external_id(
        restaurant_id=restaurant.id,
        external_order_id="non-existent-order",
    )

    assert order is None


@pytest.mark.asyncio
async def test_get_by_restaurant_order_id(
    uow: UnitOfWork,
):
    customer, restaurant, branch = await create_order_dependencies(uow)

    restaurant_order_id = f"restaurant-order-{uuid4()}"

    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        branch_id=branch.id,
        external_order_id=f"external-{uuid4()}",
        restaurant_order_id=restaurant_order_id,
        request_hash=f"hash-{uuid4()}",
        status="confirmed",
    )

    uow.orders.add(order)

    await uow.session.commit()

    saved_order = await uow.orders.get_by_restaurant_order_id(
        restaurant_id=restaurant.id,
        restaurant_order_id=restaurant_order_id,
    )

    assert saved_order is not None
    assert saved_order.id == order.id
    assert saved_order.restaurant_id == restaurant.id
    assert saved_order.restaurant_order_id == restaurant_order_id
