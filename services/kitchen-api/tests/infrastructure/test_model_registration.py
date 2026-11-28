from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import configure_mappers

from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base
from app.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


def test_all_orm_models_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "restaurants",
        "restaurant_branches",
        "menus",
        "menu_items",
        "branch_menu_items",
        "sync_snapshots",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "users",
        "user_action_tokens",
    }
    configure_mappers()


@pytest.mark.asyncio
async def test_all_repository_groups_share_one_session() -> None:
    session = AsyncMock()
    async with UnitOfWork(lambda: session) as uow:
        repositories = [
            uow.catalog.restaurants,
            uow.catalog.restaurant_branches,
            uow.catalog.menus,
            uow.catalog.menu_items,
            uow.catalog.branch_menu_items,
            uow.catalog.sync_snapshots,
            uow.cart.carts,
            uow.orders.orders,
            uow.users.users,
            uow.auth.user_action_tokens,
        ]
        assert all(repo.session is session for repo in repositories)
    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()
