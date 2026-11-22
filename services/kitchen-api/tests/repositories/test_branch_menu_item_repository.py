from uuid import uuid4

import pytest

from app.infrastructure.database.models.branch_menu_item import BranchMenuItem
from app.infrastructure.database.models.menu import Menu
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.mark.asyncio
async def test_get_by_branch_and_menu_item_returns_branch_menu_item(
    uow: UnitOfWork,
) -> None:
    restaurant = uow.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Test Restaurant",
            description="Test description",
        )
    )

    await uow.session.flush()

    branch = uow.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Test Branch",
            address="Test address",
            is_active=True,
            is_accepting_orders=True,
        )
    )

    menu = uow.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Test Menu",
        )
    )

    await uow.session.flush()

    menu_item = uow.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id=f"item-{uuid4()}",
            name="Test Item",
            description="Test description",
            price=500,
            is_active=True,
        )
    )

    await uow.session.flush()

    branch_menu_item = uow.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=True,
        )
    )

    await uow.session.flush()

    result = await uow.branch_menu_items.get_by_branch_and_menu_item(
        branch.id,
        menu_item.id,
    )

    assert result is not None
    assert result.id == branch_menu_item.id
    assert result.branch_id == branch.id
    assert result.menu_item_id == menu_item.id
    assert result.is_available is True


@pytest.mark.asyncio
async def test_get_by_branch_and_menu_item_returns_none_when_not_found(
    uow: UnitOfWork,
) -> None:
    result = await uow.branch_menu_items.get_by_branch_and_menu_item(
        uuid4(),
        uuid4(),
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_with_menu_item_loads_related_menu_item(
    uow: UnitOfWork,
) -> None:
    restaurant = uow.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Test Restaurant",
            description="Test description",
        )
    )

    await uow.session.flush()

    branch = uow.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Test Branch",
            address="Test address",
            is_active=True,
            is_accepting_orders=True,
        )
    )

    menu = uow.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Test Menu",
        )
    )

    await uow.session.flush()

    menu_item = uow.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id=f"item-{uuid4()}",
            name="Test Item",
            description="Test description",
            price=500,
            is_active=True,
        )
    )

    await uow.session.flush()

    branch_menu_item = uow.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=True,
        )
    )

    await uow.session.flush()

    result = await uow.branch_menu_items.get_with_menu_item(
        branch.id,
        menu_item.id,
    )

    assert result is not None
    assert result.id == branch_menu_item.id

    assert result.menu_item is not None
    assert result.menu_item.id == menu_item.id
    assert result.menu_item.name == "Test Item"
    assert result.menu_item.price == 500
