from uuid import uuid4

import pytest
from sqlalchemy import select

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.orders.models.order import Order
from app.modules.orders.models.order_item import OrderItem, OrderItemSnapshot
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


async def create_aggregate_dependencies(uow: UnitOfWork):
    user, restaurant, branch = await create_order_dependencies(uow)
    menu = uow.catalog.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Menu",
        )
    )
    await uow.flush()
    first = uow.catalog.menu_items.add(
        MenuItem(menu_id=menu.id, external_id=f"first-{uuid4()}", name="First")
    )
    second = uow.catalog.menu_items.add(
        MenuItem(
            menu_id=menu.id, external_id=f"second-{uuid4()}", name="Second"
        )
    )
    await uow.flush()
    return user, restaurant, branch, first, second


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


@pytest.mark.asyncio
@pytest.mark.parametrize("final_state", ["confirmed", "rejected"])
async def test_full_aggregate_persists_and_reloads_with_result(
    test_session_factory, final_state
):
    external_id = f"external-{uuid4()}"
    async with UnitOfWork(test_session_factory) as uow:
        (
            user,
            restaurant,
            branch,
            first,
            second,
        ) = await create_aggregate_dependencies(uow)
        order = Order.create_pending(
            user_id=user.id,
            restaurant_id=restaurant.id,
            branch_id=branch.id,
            external_order_id=external_id,
            request_hash="historical-hash",
            items=[
                OrderItemSnapshot(first.id, "First at purchase", 100, 2),
                OrderItemSnapshot(second.id, "Second at purchase", 250, 3),
            ],
        )
        uow.orders.orders.add(order)
        await uow.flush()
        order_id, restaurant_id = order.id, restaurant.id

    async with UnitOfWork(test_session_factory) as uow:
        loaded = await uow.orders.orders.get_with_items(order_id)
        assert loaded.status == "pending"
        assert {
            (item.product_name, item.unit_price, item.quantity)
            for item in loaded.items
        } == {("First at purchase", 100, 2), ("Second at purchase", 250, 3)}
        locked = await uow.orders.orders.get_by_external_id_for_update(
            restaurant_id, external_id
        )
        assert locked is loaded
        assert len(locked.items) == 2
        if final_state == "confirmed":
            locked.confirm("restaurant-final")
        else:
            locked.reject(
                "PRICE_CHANGED", "Price changed", "item-external", 100, 125
            )

    async with UnitOfWork(test_session_factory) as uow:
        loaded = await uow.orders.orders.get_with_items(order_id)
        assert loaded.status == final_state
        assert loaded.request_hash == "historical-hash"
        assert {
            (item.product_name, item.unit_price, item.quantity)
            for item in loaded.items
        } == {("First at purchase", 100, 2), ("Second at purchase", 250, 3)}
        if final_state == "confirmed":
            assert loaded.restaurant_order_id == "restaurant-final"
            assert loaded.rejection_code is None
        else:
            assert loaded.restaurant_order_id is None
            assert (
                loaded.rejection_code,
                loaded.rejection_message,
                loaded.rejection_menu_item_external_id,
                loaded.rejection_old_price,
                loaded.rejection_current_price,
            ) == ("PRICE_CHANGED", "Price changed", "item-external", 100, 125)


@pytest.mark.asyncio
async def test_flush_then_rollback_removes_new_aggregate(test_session_factory):
    async with UnitOfWork(test_session_factory) as uow:
        (
            user,
            restaurant,
            branch,
            first,
            _,
        ) = await create_aggregate_dependencies(uow)
        user_id, restaurant_id, branch_id, menu_item_id = (
            user.id,
            restaurant.id,
            branch.id,
            first.id,
        )
    external_id = f"external-{uuid4()}"
    order_id = None
    with pytest.raises(RuntimeError, match="creation rollback"):
        async with UnitOfWork(test_session_factory) as uow:
            order = Order.create_pending(
                user_id,
                restaurant_id,
                branch_id,
                external_id,
                "hash",
                [OrderItemSnapshot(menu_item_id, "Historical", 100, 1)],
            )
            uow.orders.orders.add(order)
            await uow.flush()
            order_id = order.id
            raise RuntimeError("creation rollback")

    async with UnitOfWork(test_session_factory) as uow:
        assert (
            await uow.orders.orders.get_by_external_id(
                restaurant_id, external_id
            )
            is None
        )
        items = await uow.session.scalars(
            select(OrderItem).where(OrderItem.order_id == order_id)
        )
        assert items.all() == []


@pytest.mark.asyncio
async def test_flush_then_rollback_restores_pending_state(
    test_session_factory,
):
    async with UnitOfWork(test_session_factory) as uow:
        (
            user,
            restaurant,
            branch,
            first,
            _,
        ) = await create_aggregate_dependencies(uow)
        order = Order.create_pending(
            user.id,
            restaurant.id,
            branch.id,
            f"external-{uuid4()}",
            "hash",
            [OrderItemSnapshot(first.id, "Historical", 100, 1)],
        )
        uow.orders.orders.add(order)
        await uow.flush()
        order_id = order.id

    with pytest.raises(RuntimeError, match="finalization rollback"):
        async with UnitOfWork(test_session_factory) as uow:
            order = await uow.orders.orders.get_with_items(order_id)
            order.confirm("restaurant-final")
            await uow.flush()
            raise RuntimeError("finalization rollback")

    async with UnitOfWork(test_session_factory) as uow:
        order = await uow.orders.orders.get_with_items(order_id)
        assert order.status == "pending"
        assert order.restaurant_order_id is None
        assert len(order.items) == 1
        assert order.items[0].product_name == "Historical"
