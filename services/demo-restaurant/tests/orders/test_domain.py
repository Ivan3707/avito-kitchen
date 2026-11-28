from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from app.modules.orders.models.restaurant_order import RestaurantOrder
from app.modules.orders.models.restaurant_order_item import (
    RestaurantOrderItemSnapshot,
)

pytestmark = pytest.mark.unit


def snapshot(*, quantity=2, unit_price=100, external_id="item-1"):
    return RestaurantOrderItemSnapshot(
        menu_item_id=uuid4(),
        menu_item_external_id=external_id,
        menu_item_name="Historical name",
        quantity=quantity,
        unit_price=unit_price,
    )


def accepted(items, branch_id=None):
    return RestaurantOrder.create_accepted(
        external_id="order-1",
        branch_id=branch_id if branch_id is not None else uuid4(),
        branch_external_id="branch-1",
        request_hash="hash",
        items=items,
    )


def rejected(**overrides):
    args = {
        "external_id": "order-1",
        "branch_id": None,
        "branch_external_id": "missing-branch",
        "request_hash": "hash",
        "code": "branch_unavailable",
        "message": "Branch is unavailable",
    }
    args.update(overrides)
    return RestaurantOrder.create_rejected(**args)


@pytest.mark.parametrize("count", [1, 3])
def test_accepted_order_contains_complete_historical_snapshot(count):
    snapshots = [snapshot(external_id=f"item-{i}") for i in range(count)]
    branch_id = uuid4()
    order = accepted(snapshots, branch_id)

    assert order.status == "accepted"
    assert order.accepted is True
    assert order.branch_id == branch_id
    assert order.external_id == "order-1"
    assert order.branch_external_id == "branch-1"
    assert order.request_hash == "hash"
    assert order.id is not None
    assert len(order.items) == count
    for item, source in zip(order.items, snapshots, strict=True):
        assert item.order is order
        assert item.order_id == order.id
        assert item.menu_item_id == source.menu_item_id
        assert item.menu_item_external_id == source.menu_item_external_id
        assert item.menu_item_name == source.menu_item_name
        assert item.quantity == source.quantity
        assert item.unit_price == source.unit_price
    assert order.rejection_code is None
    assert order.rejection_reason is None
    assert order.rejection_menu_item_external_id is None
    assert order.rejection_old_price is None
    assert order.rejection_current_price is None


def test_snapshot_is_frozen_and_source_list_changes_do_not_change_order():
    source = [snapshot()]
    order = accepted(source)
    with pytest.raises(FrozenInstanceError):
        source[0].unit_price = 50
    source.clear()
    assert len(order.items) == 1
    assert order.items[0].unit_price == 100


@pytest.mark.parametrize(
    "items",
    [
        [],
        [snapshot(quantity=0)],
        [snapshot(quantity=-1)],
        [snapshot(unit_price=0)],
        [snapshot(unit_price=-1)],
    ],
)
def test_accepted_order_rejects_invalid_items(items):
    with pytest.raises(ValueError):
        accepted(items)


def test_accepted_order_requires_branch():
    with pytest.raises(ValueError):
        RestaurantOrder.create_accepted(
            "order-1", None, "branch-1", "hash", [snapshot()]
        )


@pytest.mark.parametrize("same_internal_id", [True, False])
def test_accepted_order_rejects_duplicate_products(same_internal_id):
    first = snapshot()
    second = snapshot(external_id="item-2")
    if same_internal_id:
        second = RestaurantOrderItemSnapshot(
            first.menu_item_id,
            second.menu_item_external_id,
            second.menu_item_name,
            second.quantity,
            second.unit_price,
        )
    else:
        second = RestaurantOrderItemSnapshot(
            second.menu_item_id,
            first.menu_item_external_id,
            second.menu_item_name,
            second.quantity,
            second.unit_price,
        )
    with pytest.raises(ValueError):
        accepted([first, second])


@pytest.mark.parametrize("branch_id", [None, uuid4()])
def test_rejected_order_has_details_and_no_items(branch_id):
    order = rejected(
        branch_id=branch_id,
        menu_item_external_id="item-1",
        old_price=100,
        current_price=120,
    )
    assert order.status == "rejected"
    assert order.accepted is False
    assert order.branch_id == branch_id
    assert order.branch_external_id == "missing-branch"
    assert order.request_hash == "hash"
    assert order.rejection_code == "branch_unavailable"
    assert order.rejection_reason == "Branch is unavailable"
    assert order.rejection_menu_item_external_id == "item-1"
    assert order.rejection_old_price == 100
    assert order.rejection_current_price == 120
    assert order.items == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"code": ""},
        {"code": " "},
        {"message": ""},
        {"message": " "},
        {"old_price": 0},
        {"old_price": -1},
        {"current_price": 0},
        {"current_price": -1},
    ],
)
def test_rejected_order_requires_valid_reason_and_prices(overrides):
    with pytest.raises(ValueError):
        rejected(**overrides)
