from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.cart.models.cart import Cart
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.users.models.user import User

pytestmark = pytest.mark.integration


async def create_cart_dependencies(uow: UnitOfWork):
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
    user, _, branch = await create_cart_dependencies(uow)

    cart = Cart(
        user_id=user.id,
        branch_id=branch.id,
    )

    uow.cart.carts.add(cart)

    await uow.session.commit()

    saved_cart = await uow.cart.carts.get_by_id(cart.id)

    assert saved_cart is not None
    assert saved_cart.id == cart.id
    assert saved_cart.user_id == user.id
    assert saved_cart.branch_id == branch.id


@pytest.mark.asyncio
async def test_get_by_id_returns_none(
    uow: UnitOfWork,
):
    cart = await uow.cart.carts.get_by_id(uuid4())

    assert cart is None


@pytest.mark.asyncio
async def test_get_with_items(uow: UnitOfWork):
    user, restaurant, branch = await create_cart_dependencies(uow)

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )
    uow.catalog.menus.add(menu)

    await uow.session.flush()

    menu_item_1 = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Burger",
    )
    menu_item_2 = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Pizza",
    )
    menu_item_3 = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Salad",
    )

    uow.catalog.menu_items.add(menu_item_1)
    uow.catalog.menu_items.add(menu_item_2)
    uow.catalog.menu_items.add(menu_item_3)

    await uow.session.flush()

    cart = Cart(
        user_id=user.id,
        branch_id=branch.id,
        items=[],
    )
    uow.cart.carts.add(cart)

    await uow.session.flush()

    cart.add_item(menu_item_1, 2)
    cart.add_item(menu_item_2, 1)
    cart.add_item(menu_item_3, 3)

    await uow.session.commit()

    saved_cart = await uow.cart.carts.get_with_items(cart.id)

    assert saved_cart is not None
    assert saved_cart.id == cart.id
    assert len(saved_cart.items) == 3

    assert {item.menu_item_id for item in saved_cart.items} == {
        menu_item_1.id,
        menu_item_2.id,
        menu_item_3.id,
    }

    assert {item.quantity for item in saved_cart.items} == {1, 2, 3}


@pytest.mark.asyncio
async def test_aggregate_changes_persist_across_sessions(test_session_factory):
    async with UnitOfWork(test_session_factory) as uow:
        user, restaurant, branch = await create_cart_dependencies(uow)
        menu = uow.catalog.menus.add(
            Menu(
                restaurant_id=restaurant.id,
                external_id=f"menu-{uuid4()}",
                name="Menu",
            )
        )
        await uow.flush()
        first = uow.catalog.menu_items.add(
            MenuItem(
                menu_id=menu.id, external_id=f"first-{uuid4()}", name="First"
            )
        )
        second = uow.catalog.menu_items.add(
            MenuItem(
                menu_id=menu.id, external_id=f"second-{uuid4()}", name="Second"
            )
        )
        untouched = uow.catalog.menu_items.add(
            MenuItem(
                menu_id=menu.id,
                external_id=f"untouched-{uuid4()}",
                name="Untouched",
            )
        )
        await uow.flush()
        cart = uow.cart.carts.add(
            Cart(user_id=user.id, branch_id=branch.id, items=[])
        )
        cart.add_item(first, 2)
        cart.add_item(first, 3)
        cart.add_item(second, 4)
        cart.add_item(untouched, 7)
        await uow.flush()
        cart_id, first_id, second_id, untouched_id = (
            cart.id,
            first.id,
            second.id,
            untouched.id,
        )

    async with UnitOfWork(test_session_factory) as uow:
        cart = await uow.cart.carts.get_with_items(cart_id)
        assert {item.menu_item_id: item.quantity for item in cart.items} == {
            first_id: 5,
            second_id: 4,
            untouched_id: 7,
        }
        cart.update_item_quantity(first_id, 6)
        cart.remove_ordered_quantities({second_id: 4})

    async with UnitOfWork(test_session_factory) as uow:
        cart = await uow.cart.carts.get_with_items(cart_id)
        assert {item.menu_item_id: item.quantity for item in cart.items} == {
            first_id: 6,
            untouched_id: 7,
        }
        assert {item.menu_item.id for item in cart.items} == {
            first_id,
            untouched_id,
        }


@pytest.mark.asyncio
async def test_aggregate_mutation_rolls_back_on_exception(
    test_session_factory,
):
    async with UnitOfWork(test_session_factory) as uow:
        user, restaurant, branch = await create_cart_dependencies(uow)
        menu = uow.catalog.menus.add(
            Menu(
                restaurant_id=restaurant.id,
                external_id=f"menu-{uuid4()}",
                name="Menu",
            )
        )
        await uow.flush()
        item = uow.catalog.menu_items.add(
            MenuItem(
                menu_id=menu.id, external_id=f"item-{uuid4()}", name="Item"
            )
        )
        await uow.flush()
        cart = uow.cart.carts.add(
            Cart(user_id=user.id, branch_id=branch.id, items=[])
        )
        cart.add_item(item, 2)
        await uow.flush()
        cart_id, item_id = cart.id, item.id

    with pytest.raises(RuntimeError, match="rollback test"):
        async with UnitOfWork(test_session_factory) as uow:
            cart = await uow.cart.carts.get_with_items(cart_id)
            cart.update_item_quantity(item_id, 5)
            raise RuntimeError("rollback test")

    async with UnitOfWork(test_session_factory) as uow:
        cart = await uow.cart.carts.get_with_items(cart_id)
        assert len(cart.items) == 1
        assert cart.items[0].quantity == 2
