from types import SimpleNamespace as Obj
from uuid import uuid4

import pytest

from app.core.errors import ResourceNotFoundError
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.cart.models.cart import Cart
from app.modules.cart.schemas import AddCartItemRequest, UpdateCartItemRequest
from app.modules.cart.service import CartService
from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.users.models.user import User


@pytest.mark.asyncio
@pytest.mark.integration
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
    user = uow.users.users.add(
        User(
            email=f"user-{uuid4()}@example.com",
            password_hash="test-password-hash",
        )
    )
    restaurant = uow.catalog.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Restaurant",
            description=None,
        )
    )
    await uow.session.flush()
    branch = uow.catalog.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Branch",
            address="Address",
            is_active=True,
            is_accepting_orders=True,
        )
    )
    menu = uow.catalog.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Menu",
        )
    )
    await uow.session.flush()
    menu_item = uow.catalog.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id=f"item-{uuid4()}",
            name="Item",
            description=None,
            is_active=True,
        )
    )
    await uow.session.flush()
    uow.catalog.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=relation_available,
            price=price,
        )
    )
    cart = uow.cart.carts.add(
        Cart(user_id=user.id, branch_id=branch.id, items=[])
    )
    await uow.session.flush()
    service = CartService(lambda: UnitOfWork(uow.session_factory))
    if relation_available:
        added = await service.add_item(
            uow,
            user.id,
            branch.id,
            AddCartItemRequest(menu_item_id=menu_item.id, quantity=2),
        )
        assert added.items[0].quantity == 2
    else:
        cart.add_item(menu_item, 2)
        await uow.session.flush()
    response = await service.get_cart(uow, user.id, branch.id)

    assert response.items[0].price == price
    assert response.items[0].is_available is expected_available

    updated = await service.update_item(
        uow,
        user.id,
        branch.id,
        menu_item.id,
        UpdateCartItemRequest(quantity=3),
    )
    assert updated.items[0].quantity == 3
    removed = await service.remove_item(uow, user.id, branch.id, menu_item.id)
    assert removed.items == []


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize("operation", ["update", "remove"])
async def test_missing_cart_item_maps_domain_error_to_api_error(operation):
    cart = Cart(user_id=uuid4(), branch_id=uuid4(), items=[])

    class Carts:
        async def get_by_user_and_branch(self, **kwargs):
            return cart

    uow = Obj(cart=Obj(carts=Carts()))
    service = CartService(lambda: uow)
    with pytest.raises(ResourceNotFoundError, match="Cart item not found"):
        if operation == "update":
            await service.update_item(
                uow,
                cart.user_id,
                cart.branch_id,
                uuid4(),
                UpdateCartItemRequest(quantity=2),
            )
        else:
            await service.remove_item(
                uow, cart.user_id, cart.branch_id, uuid4()
            )
    assert cart.items == []
