from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_by_branch_and_menu_item_returns_branch_menu_item(
    uow: UnitOfWork,
) -> None:
    restaurant = uow.catalog.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Test Restaurant",
            description="Test description",
        )
    )

    await uow.session.flush()

    branch = uow.catalog.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Test Branch",
            address="Test address",
            is_active=True,
            is_accepting_orders=True,
        )
    )

    menu = uow.catalog.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Test Menu",
        )
    )

    await uow.session.flush()

    menu_item = uow.catalog.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id=f"item-{uuid4()}",
            name="Test Item",
            description="Test description",
            is_active=True,
        )
    )

    await uow.session.flush()

    branch_menu_item = uow.catalog.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=True,
            price=500,
        )
    )

    await uow.session.flush()

    result = await uow.catalog.branch_menu_items.get_by_branch_and_menu_item(
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
    result = await uow.catalog.branch_menu_items.get_by_branch_and_menu_item(
        uuid4(),
        uuid4(),
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_with_menu_item_loads_related_menu_item(
    uow: UnitOfWork,
) -> None:
    restaurant = uow.catalog.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Test Restaurant",
            description="Test description",
        )
    )

    await uow.session.flush()

    branch = uow.catalog.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Test Branch",
            address="Test address",
            is_active=True,
            is_accepting_orders=True,
        )
    )

    menu = uow.catalog.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Test Menu",
        )
    )

    await uow.session.flush()

    menu_item = uow.catalog.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id=f"item-{uuid4()}",
            name="Test Item",
            description="Test description",
            is_active=True,
        )
    )

    await uow.session.flush()

    branch_menu_item = uow.catalog.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=True,
            price=500,
        )
    )

    await uow.session.flush()

    result = await uow.catalog.branch_menu_items.get_with_menu_item(
        branch.id,
        menu_item.id,
    )

    assert result is not None
    assert result.id == branch_menu_item.id

    assert result.menu_item is not None
    assert result.menu_item.id == menu_item.id
    assert result.menu_item.name == "Test Item"
    assert result.price == 500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("price", "is_available"),
    [(0, False), (None, True)],
)
async def test_branch_menu_item_price_constraints(
    uow: UnitOfWork,
    price: int | None,
    is_available: bool,
) -> None:
    restaurant = uow.catalog.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Test Restaurant",
            description=None,
        )
    )
    await uow.session.flush()
    branch = uow.catalog.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Test Branch",
            address="Test address",
            is_active=True,
            is_accepting_orders=True,
        )
    )
    menu = uow.catalog.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Test Menu",
        )
    )
    await uow.session.flush()
    menu_item = uow.catalog.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id=f"item-{uuid4()}",
            name="Test Item",
            description=None,
            is_active=True,
        )
    )
    await uow.session.flush()
    uow.catalog.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=is_available,
            price=price,
        )
    )

    with pytest.raises(IntegrityError):
        await uow.session.flush()
    await uow.session.rollback()
