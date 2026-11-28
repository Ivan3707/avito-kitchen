from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_add_and_get_by_id(uow: UnitOfWork):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.catalog.restaurants.add(restaurant)
    await uow.session.flush()

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )

    uow.catalog.menus.add(menu)
    await uow.session.flush()

    menu_item = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Pizza",
    )

    uow.catalog.menu_items.add(menu_item)

    await uow.session.commit()

    saved_item = await uow.catalog.menu_items.get_by_id(menu_item.id)

    assert saved_item is not None
    assert saved_item.id == menu_item.id
    assert saved_item.menu_id == menu.id
    assert saved_item.external_id == menu_item.external_id
    assert saved_item.name == "Pizza"


@pytest.mark.asyncio
async def test_get_by_menu_and_external_id(uow: UnitOfWork):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.catalog.restaurants.add(restaurant)
    await uow.session.flush()

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )

    uow.catalog.menus.add(menu)
    await uow.session.flush()

    menu_item = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Burger",
    )

    uow.catalog.menu_items.add(menu_item)

    await uow.session.commit()

    saved_item = await uow.catalog.menu_items.get_by_menu_and_external_id(
        menu_id=menu.id,
        external_id=menu_item.external_id,
    )

    assert saved_item is not None
    assert saved_item.id == menu_item.id
    assert saved_item.menu_id == menu.id
    assert saved_item.external_id == menu_item.external_id


@pytest.mark.asyncio
async def test_get_by_menu_and_external_id_returns_none(
    uow: UnitOfWork,
):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.catalog.restaurants.add(restaurant)
    await uow.session.flush()

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )

    uow.catalog.menus.add(menu)
    await uow.session.flush()

    saved_item = await uow.catalog.menu_items.get_by_menu_and_external_id(
        menu_id=menu.id,
        external_id="non-existent-item",
    )

    assert saved_item is None
