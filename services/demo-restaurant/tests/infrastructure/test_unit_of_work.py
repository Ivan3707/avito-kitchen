from unittest.mock import AsyncMock

import pytest

from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base
from app.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_repository_groups_share_one_session() -> None:
    session = AsyncMock()
    async with UnitOfWork(lambda: session) as uow:
        repositories = (
            uow.catalog.restaurant_branches,
            uow.catalog.menu_items,
            uow.catalog.branch_menu_items,
            uow.catalog.catalog_state,
            uow.orders.restaurant_orders,
            uow.orders.restaurant_order_items,
        )
        assert all(
            repository.session is session for repository in repositories
        )
    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()


def test_all_models_are_registered_and_relationships_resolve() -> None:
    from sqlalchemy.orm import configure_mappers

    assert set(Base.metadata.tables) == {
        "restaurant_branches",
        "menu_items",
        "branch_menu_items",
        "catalog_state",
        "restaurant_orders",
        "restaurant_order_items",
    }
    configure_mappers()
