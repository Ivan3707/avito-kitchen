from uuid import uuid4

import pytest

from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.orders.schemas import BusinessErrorCode, RestaurantOrder
from app.modules.orders.service import OrderService

pytestmark = pytest.mark.unit


class Repository:
    def __init__(self, values=None, key="external_id"):
        self.values = values if values is not None else []
        self.key = key

    async def lock_external_id(self, external_id):
        return None

    async def get_by_external_id(self, external_id):
        return next(
            (
                value
                for value in self.values
                if getattr(value, self.key) == external_id
            ),
            None,
        )

    def add(self, value):
        if getattr(value, "id", None) is None:
            value.id = uuid4()
        self.values.append(value)
        return value


class BranchItemRepository(Repository):
    async def get_by_branch_and_menu_item(self, branch_id, menu_item_id):
        return next(
            (
                value
                for value in self.values
                if value.branch_id == branch_id
                and value.menu_item_id == menu_item_id
            ),
            None,
        )


class FakeUow:
    orders = []
    order_items = []
    relation_price = 100
    relation_available = True
    include_relation = True

    def __init__(self, session_factory):
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
            name="Item",
            description=None,
            is_active=True,
        )
        relation = BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=item.id,
            is_available=self.relation_available,
            price=self.relation_price,
        )
        self.catalog = type("CatalogGroup", (), {})()
        self.orders = type("OrderGroup", (), {})()
        self.catalog.restaurant_branches = Repository([branch])
        self.catalog.menu_items = Repository([item])
        self.catalog.branch_menu_items = BranchItemRepository(
            [relation] if self.include_relation else []
        )
        self.orders.restaurant_orders = Repository(type(self).orders)
        self.orders.restaurant_order_items = Repository(self.order_items)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def flush(self):
        return None


def order(
    *, price=100, order_id="order-1", branch_external_id="branch-1"
) -> RestaurantOrder:
    return RestaurantOrder(
        order_id=order_id,
        branch_external_id=branch_external_id,
        items=[
            {
                "menu_item_external_id": "item-1",
                "quantity": 1,
                "unit_price": price,
            }
        ],
    )


@pytest.mark.asyncio
async def test_create_order_is_idempotent(monkeypatch) -> None:
    FakeUow.orders = []
    FakeUow.order_items = []
    monkeypatch.setattr("app.modules.orders.service.UnitOfWork", FakeUow)
    service = OrderService(object())
    first = await service.create_order(order())
    second = await service.create_order(order())
    assert first.accepted is True
    assert second.restaurant_order_id == first.restaurant_order_id
    assert len(FakeUow.orders) == 1
    assert FakeUow.order_items[0].unit_price == 100


@pytest.mark.asyncio
async def test_same_order_id_with_different_payload_conflicts(
    monkeypatch,
) -> None:
    FakeUow.orders = []
    monkeypatch.setattr("app.modules.orders.service.UnitOfWork", FakeUow)
    service = OrderService(object())
    await service.create_order(order())
    response = await service.create_order(order(price=101))
    assert response.accepted is False
    assert response.reason.code == BusinessErrorCode.ORDER_ID_CONFLICT


@pytest.mark.asyncio
async def test_price_change_is_rejected(monkeypatch) -> None:
    FakeUow.orders = []
    monkeypatch.setattr("app.modules.orders.service.UnitOfWork", FakeUow)
    response = await OrderService(object()).create_order(order(price=101))
    assert response.accepted is False
    assert response.reason.code == BusinessErrorCode.PRICE_CHANGED


@pytest.mark.asyncio
async def test_item_without_branch_price_is_unavailable(monkeypatch) -> None:
    FakeUow.orders = []
    monkeypatch.setattr(FakeUow, "relation_price", None)
    monkeypatch.setattr(FakeUow, "relation_available", False)
    monkeypatch.setattr("app.modules.orders.service.UnitOfWork", FakeUow)
    response = await OrderService(object()).create_order(order())
    assert response.accepted is False
    assert response.reason.code == BusinessErrorCode.PRODUCT_UNAVAILABLE


@pytest.mark.asyncio
async def test_missing_branch_item_relation_is_unavailable(
    monkeypatch,
) -> None:
    FakeUow.orders = []
    monkeypatch.setattr(FakeUow, "include_relation", False)
    monkeypatch.setattr("app.modules.orders.service.UnitOfWork", FakeUow)
    response = await OrderService(object()).create_order(order())
    assert response.accepted is False
    assert response.reason.code == BusinessErrorCode.PRODUCT_UNAVAILABLE


@pytest.mark.asyncio
async def test_unknown_branch_rejection_is_idempotent(monkeypatch) -> None:
    FakeUow.orders = []
    monkeypatch.setattr("app.modules.orders.service.UnitOfWork", FakeUow)
    service = OrderService(object())
    first = await service.create_order(
        order(branch_external_id="unknown-branch")
    )
    repeated = await service.create_order(
        order(branch_external_id="unknown-branch")
    )
    conflict = await service.create_order(
        order(branch_external_id="another-branch")
    )
    assert first.reason.code == BusinessErrorCode.BRANCH_UNAVAILABLE
    assert repeated.reason == first.reason
    assert conflict.reason.code == BusinessErrorCode.ORDER_ID_CONFLICT
    assert len(FakeUow.orders) == 1
