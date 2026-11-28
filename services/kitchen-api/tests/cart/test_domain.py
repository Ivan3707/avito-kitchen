from uuid import uuid4

import pytest

from app.modules.cart.errors import CartItemNotFoundError
from app.modules.cart.models.cart import Cart
from app.modules.catalog.models.menu_item import MenuItem

pytestmark = pytest.mark.unit


def make_cart() -> Cart:
    return Cart(user_id=uuid4(), branch_id=uuid4(), items=[])


def make_menu_item() -> MenuItem:
    return MenuItem(
        id=uuid4(), menu_id=uuid4(), external_id="item", name="Item"
    )


def test_add_item_to_empty_cart_sets_identity_and_relationship():
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    assert len(cart.items) == 1
    assert cart.items[0].menu_item_id == menu_item.id
    assert cart.items[0].menu_item is menu_item
    assert cart.items[0].quantity == 2


def test_repeated_add_before_flush_does_not_duplicate_item():
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    cart.add_item(menu_item, 3)
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 5


def test_add_different_items_keeps_each_quantity():
    cart, first, second = make_cart(), make_menu_item(), make_menu_item()
    cart.add_item(first, 2)
    cart.add_item(second, 3)
    assert {item.menu_item_id: item.quantity for item in cart.items} == {
        first.id: 2,
        second.id: 3,
    }


def test_update_existing_item():
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    cart.update_item_quantity(menu_item.id, 4)
    assert cart.items[0].quantity == 4


@pytest.mark.parametrize("quantity", [0, -1])
def test_add_rejects_nonpositive_quantity_without_mutation(quantity):
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    with pytest.raises(ValueError, match="positive"):
        cart.add_item(menu_item, quantity)
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2


@pytest.mark.parametrize("quantity", [0, -1])
def test_update_rejects_nonpositive_quantity_without_mutation(quantity):
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    with pytest.raises(ValueError, match="positive"):
        cart.update_item_quantity(menu_item.id, quantity)
    assert cart.items[0].quantity == 2


def test_update_missing_item_does_not_create_one():
    cart, menu_item = make_cart(), make_menu_item()
    with pytest.raises(CartItemNotFoundError):
        cart.update_item_quantity(menu_item.id, 2)
    assert cart.items == []


def test_remove_existing_item_keeps_other_item():
    cart, first, second = make_cart(), make_menu_item(), make_menu_item()
    cart.add_item(first, 2)
    cart.add_item(second, 3)
    cart.remove_item(first.id)
    assert len(cart.items) == 1
    assert cart.items[0].menu_item_id == second.id
    assert cart.items[0].quantity == 3


def test_remove_missing_item_preserves_cart():
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    with pytest.raises(CartItemNotFoundError):
        cart.remove_item(uuid4())
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2


@pytest.mark.parametrize(
    ("current", "ordered", "remaining"),
    [(2, 2, None), (5, 2, 3), (2, 3, None)],
)
def test_remove_ordered_quantities_current_equal_more_or_less(
    current, ordered, remaining
):
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, current)
    cart.remove_ordered_quantities({menu_item.id: ordered})
    assert [item.quantity for item in cart.items] == (
        [] if remaining is None else [remaining]
    )


def test_remove_ordered_quantities_preserves_unordered_and_missing_items():
    cart, ordered, other = make_cart(), make_menu_item(), make_menu_item()
    cart.add_item(ordered, 4)
    cart.add_item(other, 3)
    cart.remove_ordered_quantities({ordered.id: 2, uuid4(): 5})
    assert {item.menu_item_id: item.quantity for item in cart.items} == {
        ordered.id: 2,
        other.id: 3,
    }


@pytest.mark.parametrize("ordered_quantities", [{}, {uuid4(): 2}])
def test_empty_or_missing_ordered_items_do_not_change_cart(ordered_quantities):
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    cart.remove_ordered_quantities(ordered_quantities)
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2


def test_zero_ordered_quantity_does_not_change_cart():
    cart, menu_item = make_cart(), make_menu_item()
    cart.add_item(menu_item, 2)
    cart.remove_ordered_quantities({menu_item.id: 0})
    assert cart.items[0].quantity == 2


def test_negative_ordered_quantity_rejects_entire_batch_before_mutation():
    cart, first, second = make_cart(), make_menu_item(), make_menu_item()
    cart.add_item(first, 2)
    cart.add_item(second, 3)
    with pytest.raises(ValueError, match="negative"):
        cart.remove_ordered_quantities({first.id: 2, second.id: -1})
    assert {item.menu_item_id: item.quantity for item in cart.items} == {
        first.id: 2,
        second.id: 3,
    }
