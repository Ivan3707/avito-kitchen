from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.restaurant import (
    Restaurant,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_add_and_get_by_id(
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

    await uow.session.commit()

    saved_menu = await uow.catalog.menus.get_by_id(menu.id)

    assert saved_menu is not None
    assert saved_menu.id == menu.id
    assert saved_menu.restaurant_id == restaurant.id
    assert saved_menu.external_id == menu.external_id


@pytest.mark.asyncio
async def test_get_by_restaurant_id(
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

    await uow.session.commit()

    saved_menu = await uow.catalog.menus.get_by_restaurant_id(restaurant.id)

    assert saved_menu is not None
    assert saved_menu.id == menu.id
    assert saved_menu.restaurant_id == restaurant.id


@pytest.mark.asyncio
async def test_get_by_restaurant_id_returns_none(
    uow: UnitOfWork,
):
    restaurant = Restaurant(
        external_id=f"restaurant-{uuid4()}",
        name="Test Restaurant",
    )

    uow.catalog.restaurants.add(restaurant)

    await uow.session.commit()

    menu = await uow.catalog.menus.get_by_restaurant_id(restaurant.id)

    assert menu is None
