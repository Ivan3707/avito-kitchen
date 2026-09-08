from uuid import uuid4

import pytest

from app.infrastructure.database.models.menu import Menu
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.mark.asyncio
async def test_add_and_get_by_id(uow: UnitOfWork):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.restaurants.add(restaurant)
    await uow.session.flush()

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )

    uow.menus.add(menu)
    await uow.session.flush()

    menu_item = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Pizza",
        price=1000,
    )

    uow.menu_items.add(menu_item)

    await uow.session.commit()

    saved_item = await uow.menu_items.get_by_id(menu_item.id)

    assert saved_item is not None
    assert saved_item.id == menu_item.id
    assert saved_item.menu_id == menu.id
    assert saved_item.external_id == menu_item.external_id
    assert saved_item.name == "Pizza"
    assert saved_item.price == 1000


@pytest.mark.asyncio
async def test_get_by_menu_and_external_id(uow: UnitOfWork):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.restaurants.add(restaurant)
    await uow.session.flush()

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )

    uow.menus.add(menu)
    await uow.session.flush()

    menu_item = MenuItem(
        menu_id=menu.id,
        external_id=f"item-{uuid4()}",
        name="Burger",
        price=750,
    )

    uow.menu_items.add(menu_item)

    await uow.session.commit()

    saved_item = await uow.menu_items.get_by_menu_and_external_id(
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

    uow.restaurants.add(restaurant)
    await uow.session.flush()

    menu = Menu(
        restaurant_id=restaurant.id,
        external_id=f"menu-{uuid4()}",
        name="Test Menu",
    )

    uow.menus.add(menu)
    await uow.session.flush()

    saved_item = await uow.menu_items.get_by_menu_and_external_id(
        menu_id=menu.id,
        external_id="non-existent-item",
    )

    assert saved_item is None
