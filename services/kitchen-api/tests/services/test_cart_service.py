from uuid import uuid4

import pytest

from app.infrastructure.database.models.branch_menu_item import BranchMenuItem
from app.infrastructure.database.models.cart import Cart
from app.infrastructure.database.models.cart_item import CartItem
from app.infrastructure.database.models.menu import Menu
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.database.models.user import User
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.cart import CartService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("price", "relation_available", "expected_available"),
    [(175, True, True), (None, False, False)],
)
async def test_cart_uses_selected_branch_price(
    uow: UnitOfWork,
    price: int | None,
    relation_available: bool,
    expected_available: bool,
) -> None:
    user = uow.users.add(
        User(
            email=f"user-{uuid4()}@example.com",
            password_hash="test-password-hash",
        )
    )
    restaurant = uow.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Restaurant",
            description=None,
        )
    )
    await uow.session.flush()
    branch = uow.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Branch",
            address="Address",
            is_active=True,
            is_accepting_orders=True,
        )
    )
    menu = uow.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Menu",
        )
    )
    await uow.session.flush()
    menu_item = uow.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id=f"item-{uuid4()}",
            name="Item",
            description=None,
            is_active=True,
        )
    )
    await uow.session.flush()
    uow.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=relation_available,
            price=price,
        )
    )
    cart = uow.carts.add(
        Cart(user_id=user.id, branch_id=branch.id)
    )
    await uow.session.flush()
    uow.session.add(
        CartItem(
            cart_id=cart.id,
            menu_item_id=menu_item.id,
            quantity=2,
        )
    )
    await uow.session.flush()

    response = await CartService().get_cart(uow, user.id, branch.id)

    assert response.items[0].price == price
    assert response.items[0].is_available is expected_available
