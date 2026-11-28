from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from app.modules.orders.errors import InvalidOrderTransitionError
from app.modules.orders.models.order import Order
from app.modules.orders.models.order_item import OrderItemSnapshot

pytestmark = pytest.mark.unit


def snapshot(**changes):
    values = {
        "menu_item_id": uuid4(),
        "product_name": "Historical name",
        "unit_price": 100,
        "quantity": 2,
    }
    values.update(changes)
    return OrderItemSnapshot(**values)


def create_order(items=None):
    return Order.create_pending(
        user_id=uuid4(),
        restaurant_id=uuid4(),
        branch_id=uuid4(),
        external_order_id="external-1",
        request_hash="hash-1",
        items=[snapshot()] if items is None else items,
    )


def identity_and_items(order):
    return (
        order.id,
        order.user_id,
        order.restaurant_id,
        order.branch_id,
        order.external_order_id,
        order.request_hash,
        [
            (
                item.menu_item_id,
                item.product_name,
                item.unit_price,
                item.quantity,
            )
            for item in order.items
        ],
    )


def result_state(order):
    return (
        order.status,
        order.restaurant_order_id,
        order.rejection_code,
        order.rejection_message,
        order.rejection_menu_item_external_id,
        order.rejection_old_price,
        order.rejection_current_price,
    )


def test_create_pending_has_identity_historical_item_and_no_result():
    source = snapshot()
    order = create_order([source])
    assert order.id is not None
    assert order.status == "pending"
    assert len(order.items) == 1
    item = order.items[0]
    assert item.order is order
    assert item.order_id == order.id
    assert item.menu_item_id == source.menu_item_id
    assert (item.product_name, item.unit_price, item.quantity) == (
        "Historical name",
        100,
        2,
    )
    assert result_state(order) == (
        "pending",
        None,
        None,
        None,
        None,
        None,
        None,
    )


def test_create_pending_copies_multiple_input_snapshots():
    first, second = snapshot(), snapshot(product_name="Second", unit_price=200)
    source = [first, second]
    order = create_order(source)
    source.clear()
    assert [item.product_name for item in order.items] == [
        "Historical name",
        "Second",
    ]
    assert [item.unit_price for item in order.items] == [100, 200]
    with pytest.raises(FrozenInstanceError):
        first.quantity = 9


def test_create_pending_rejects_empty_items():
    with pytest.raises(ValueError, match="at least one"):
        create_order([])


@pytest.mark.parametrize("quantity", [0, -1])
def test_create_pending_rejects_invalid_quantity(quantity):
    with pytest.raises(ValueError, match="quantity"):
        create_order([snapshot(quantity=quantity)])


@pytest.mark.parametrize("price", [0, -1])
def test_create_pending_rejects_invalid_price(price):
    with pytest.raises(ValueError, match="price"):
        create_order([snapshot(unit_price=price)])


def test_create_pending_rejects_duplicate_menu_item():
    first = snapshot()
    with pytest.raises(ValueError, match="duplicate"):
        create_order([first, snapshot(menu_item_id=first.menu_item_id)])


def test_confirm_sets_result_without_changing_identity_or_items():
    order = create_order()
    before = identity_and_items(order)
    order.confirm("restaurant-1")
    assert result_state(order) == (
        "confirmed",
        "restaurant-1",
        None,
        None,
        None,
        None,
        None,
    )
    assert identity_and_items(order) == before


@pytest.mark.parametrize("restaurant_order_id", ["", "   "])
def test_confirm_rejects_empty_restaurant_id_without_mutation(
    restaurant_order_id,
):
    order = create_order()
    before = result_state(order), identity_and_items(order)
    with pytest.raises(ValueError, match="nonempty"):
        order.confirm(restaurant_order_id)
    assert (result_state(order), identity_and_items(order)) == before


def test_reject_saves_all_details_without_changing_identity_or_items():
    order = create_order()
    before = identity_and_items(order)
    order.reject("PRICE_CHANGED", "Price changed", "external-item", 100, 125)
    assert result_state(order) == (
        "rejected",
        None,
        "PRICE_CHANGED",
        "Price changed",
        "external-item",
        100,
        125,
    )
    assert identity_and_items(order) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"code": ""},
        {"code": "  "},
        {"message": ""},
        {"message": "  "},
        {"old_price": 0},
        {"old_price": -1},
        {"current_price": 0},
        {"current_price": -1},
    ],
)
def test_reject_invalid_details_leave_order_unchanged(changes):
    order = create_order()
    before = result_state(order), identity_and_items(order)
    details = {"code": "REJECTED", "message": "Rejected", **changes}
    with pytest.raises(ValueError):
        order.reject(**details)
    assert (result_state(order), identity_and_items(order)) == before


@pytest.mark.parametrize(
    ("first_transition", "second_transition"),
    [
        ("confirm", "confirm"),
        ("confirm", "reject"),
        ("reject", "confirm"),
        ("reject", "reject"),
    ],
)
def test_completed_order_cannot_transition_again(
    first_transition, second_transition
):
    order = create_order()
    if first_transition == "confirm":
        order.confirm("restaurant-1")
    else:
        order.reject("REJECTED", "Rejected")
    before = result_state(order), identity_and_items(order)
    with pytest.raises(InvalidOrderTransitionError):
        if second_transition == "confirm":
            order.confirm("restaurant-2")
        else:
            order.reject("OTHER", "Other")
    assert (result_state(order), identity_and_items(order)) == before
