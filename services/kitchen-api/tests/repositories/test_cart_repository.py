from uuid import uuid4

import pytest

from app.infrastructure.database.models.cart import Cart
from app.infrastructure.database.models.cart_item import CartItem
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.menu import Menu
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.unit_of_work import UnitOfWork


async def create_cart_dependencies(uow: UnitOfWork):
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
    customer, _, branch = await create_cart_dependencies(uow)

    cart = Cart(
        customer_id=customer.id,
        branch_id=branch.id,
    )

    uow.carts.add(cart)

    await uow.session.commit()

    saved_cart = await uow.carts.get_by_id(cart.id)

    assert saved_cart is not None
    assert saved_cart.id == cart.id
    assert saved_cart.customer_id == customer.id
    assert saved_cart.branch_id == branch.id


@pytest.mark.asyncio
async def test_get_by_id_returns_none(
    uow: UnitOfWork,
):
    cart = await uow.carts.get_by_id(uuid4())

    assert cart is None


@pytest.mark.asyncio
async def test_get_with_items(uow: UnitOfWork):
    customer, restaurant, branch = await create_cart_dependencies(uow)

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )
    uow.menus.add(menu)

    await uow.session.flush()

    menu_item_1 = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Burger",
        price=500,
    )
    menu_item_2 = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Pizza",
        price=700,
    )
    menu_item_3 = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Salad",
        price=300,
    )

    uow.menu_items.add(menu_item_1)
    uow.menu_items.add(menu_item_2)
    uow.menu_items.add(menu_item_3)

    await uow.session.flush()

    cart = Cart(
        customer_id=customer.id,
        branch_id=branch.id,
    )
    uow.carts.add(cart)

    await uow.session.flush()

    cart_item_1 = CartItem(
        cart_id=cart.id,
        menu_item_id=menu_item_1.id,
        quantity=2,
    )
    cart_item_2 = CartItem(
        cart_id=cart.id,
        menu_item_id=menu_item_2.id,
        quantity=1,
    )
    cart_item_3 = CartItem(
        cart_id=cart.id,
        menu_item_id=menu_item_3.id,
        quantity=3,
    )

    uow.session.add_all(
        [
            cart_item_1,
            cart_item_2,
            cart_item_3,
        ]
    )

    await uow.session.commit()

    saved_cart = await uow.carts.get_with_items(cart.id)

    assert saved_cart is not None
    assert saved_cart.id == cart.id
    assert len(saved_cart.items) == 3

    assert {item.menu_item_id for item in saved_cart.items} == {
        menu_item_1.id,
        menu_item_2.id,
        menu_item_3.id,
    }

    assert {item.quantity for item in saved_cart.items} == {1, 2, 3}
