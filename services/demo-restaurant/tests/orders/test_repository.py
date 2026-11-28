from uuid import uuid4

import pytest
from sqlalchemy import select

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant_branch import RestaurantBranch
from app.modules.orders.models.restaurant_order import RestaurantOrder
from app.modules.orders.models.restaurant_order_item import (
    RestaurantOrderItem,
    RestaurantOrderItemSnapshot,
)

pytestmark = pytest.mark.integration


async def seed_catalog(factory):
    branch = RestaurantBranch(
        id=uuid4(),
        external_id="branch-1",
        name="Branch",
        address="Address",
        is_active=True,
        is_accepting_orders=True,
        branch_version=1,
    )
    item = MenuItem(
        id=uuid4(),
        external_id="item-1",
        name="Original name",
        description=None,
        is_active=True,
    )
    async with UnitOfWork(factory) as uow:
        uow.catalog.restaurant_branches.add(branch)
        uow.catalog.menu_items.add(item)
        uow.catalog.branch_menu_items.add(
            BranchMenuItem(
                branch_id=branch.id,
                menu_item_id=item.id,
                is_available=True,
                price=100,
            )
        )
    return branch, item


def accepted(branch, item, *, external_id="order-1"):
    return RestaurantOrder.create_accepted(
        external_id=external_id,
        branch_id=branch.id,
        branch_external_id=branch.external_id,
        request_hash="hash",
        items=[
            RestaurantOrderItemSnapshot(
                menu_item_id=item.id,
                menu_item_external_id=item.external_id,
                menu_item_name=item.name,
                quantity=2,
                unit_price=100,
            )
        ],
    )


@pytest.mark.asyncio
async def test_accepted_aggregate_persists_and_loads_in_new_session(
    clean_catalog_database,
):
    factory = clean_catalog_database
    branch, item = await seed_catalog(factory)
    order = accepted(branch, item)
    async with UnitOfWork(factory) as uow:
        uow.orders.restaurant_orders.add(order)
        await uow.flush()
        assert order.items[0].order_id == order.id

    async with UnitOfWork(factory) as uow:
        loaded = (
            await uow.orders.restaurant_orders.get_with_items_by_external_id(
                "order-1"
            )
        )
        assert loaded is not None
        assert loaded.id == order.id
        assert loaded.accepted is True
        assert len(loaded.items) == 1
        assert loaded.items[0].order_id == loaded.id
        assert loaded.items[0].menu_item_id == item.id
        assert loaded.items[0].quantity == 2
        assert loaded.items[0].unit_price == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("known_branch", [True, False])
async def test_rejected_aggregate_persists_details_without_items(
    clean_catalog_database,
    known_branch,
):
    factory = clean_catalog_database
    branch, _ = await seed_catalog(factory)
    order = RestaurantOrder.create_rejected(
        external_id="rejected-1",
        branch_id=branch.id if known_branch else None,
        branch_external_id="branch-1" if known_branch else "unknown-branch",
        request_hash="rejected-hash",
        code="price_changed",
        message="Product price has changed",
        menu_item_external_id="item-1",
        old_price=100,
        current_price=120,
    )
    async with UnitOfWork(factory) as uow:
        uow.orders.restaurant_orders.add(order)

    async with UnitOfWork(factory) as uow:
        loaded = (
            await uow.orders.restaurant_orders.get_with_items_by_external_id(
                "rejected-1"
            )
        )
        assert loaded is not None
        assert loaded.branch_id == order.branch_id
        assert loaded.branch_external_id == order.branch_external_id
        assert loaded.request_hash == "rejected-hash"
        assert loaded.status == "rejected"
        assert loaded.accepted is False
        assert loaded.rejection_code == "price_changed"
        assert loaded.rejection_reason == "Product price has changed"
        assert loaded.rejection_menu_item_external_id == "item-1"
        assert loaded.rejection_old_price == 100
        assert loaded.rejection_current_price == 120
        assert loaded.items == []


@pytest.mark.asyncio
async def test_rollback_after_flush_discards_root_and_children(
    clean_catalog_database,
):
    factory = clean_catalog_database
    branch, item = await seed_catalog(factory)
    with pytest.raises(RuntimeError, match="rollback requested"):
        async with UnitOfWork(factory) as uow:
            uow.orders.restaurant_orders.add(accepted(branch, item))
            await uow.flush()
            children = await uow.session.scalars(select(RestaurantOrderItem))
            assert len(children.all()) == 1
            raise RuntimeError("rollback requested")

    async with UnitOfWork(factory) as uow:
        assert (
            await uow.orders.restaurant_orders.get_by_external_id("order-1")
            is None
        )
        children = await uow.session.scalars(select(RestaurantOrderItem))
        assert children.all() == []


@pytest.mark.asyncio
async def test_catalog_change_does_not_change_order_snapshot(
    clean_catalog_database,
):
    factory = clean_catalog_database
    branch, item = await seed_catalog(factory)
    async with UnitOfWork(factory) as uow:
        uow.orders.restaurant_orders.add(accepted(branch, item))

    async with UnitOfWork(factory) as uow:
        catalog_item = await uow.catalog.menu_items.get_by_external_id(
            "item-1"
        )
        catalog_item.name = "New name"
        relation = (
            await uow.catalog.branch_menu_items.get_by_branch_and_menu_item(
                branch.id, item.id
            )
        )
        relation.price = 120

    async with UnitOfWork(factory) as uow:
        loaded = (
            await uow.orders.restaurant_orders.get_with_items_by_external_id(
                "order-1"
            )
        )
        assert loaded.items[0].menu_item_name == "Original name"
        assert loaded.items[0].unit_price == 100
