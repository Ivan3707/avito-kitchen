from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.catalog.service import CatalogService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_branch_menus_expose_branch_specific_prices(
    uow: UnitOfWork,
) -> None:
    restaurant = uow.catalog.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Restaurant",
            description=None,
        )
    )
    await uow.session.flush()
    branches = [
        uow.catalog.restaurant_branches.add(
            RestaurantBranch(
                restaurant_id=restaurant.id,
                external_id=f"branch-{uuid4()}",
                name=name,
                address="Address",
                is_active=True,
                is_accepting_orders=True,
            )
        )
        for name in ("First", "Second")
    ]
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
    for branch, price in zip(branches, (100, 175), strict=True):
        uow.catalog.branch_menu_items.add(
            BranchMenuItem(
                branch_id=branch.id,
                menu_item_id=menu_item.id,
                is_available=True,
                price=price,
            )
        )
    await uow.session.flush()

    service = CatalogService()
    first = await service.get_branch_menu(uow, branches[0].id)
    second = await service.get_branch_menu(uow, branches[1].id)

    assert first.items[0].price == 100
    assert first.items[0].is_available is True
    assert second.items[0].price == 175
    assert second.items[0].is_available is True


@pytest.mark.asyncio
async def test_unpriced_branch_item_is_reported_unavailable(
    uow: UnitOfWork,
) -> None:
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
            is_available=False,
            price=None,
        )
    )
    await uow.session.flush()

    response = await CatalogService().get_branch_menu(uow, branch.id)

    assert response.items[0].price is None
    assert response.items[0].is_available is False
