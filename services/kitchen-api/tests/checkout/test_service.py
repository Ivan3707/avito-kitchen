from types import SimpleNamespace as Obj
from uuid import uuid4

import pytest

from app.modules.cart.models.cart import Cart
from app.modules.cart.models.cart_item import CartItem
from app.modules.cart.service import CartService
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.checkout.schemas import CheckoutRequest
from app.modules.checkout.service import CheckoutService

pytestmark = pytest.mark.unit


class Repo:
    def __init__(self, value):
        self.value = value

    async def get_by_email(self, *args):
        return self.value

    async def get_by_id(self, *args):
        return self.value

    async def get_by_user_and_branch_for_update(self, *args):
        return self.value

    async def get_by_branch_and_menu_item(self, *args):
        return self.value


class FakeUow:
    active = 0

    def __init__(self, user, branch, restaurant, cart, relation):
        self.users = Obj(users=Repo(user))
        self.catalog = Obj(
            restaurant_branches=Repo(branch),
            restaurants=Repo(restaurant),
            branch_menu_items=Repo(relation),
        )
        self.cart = Obj(carts=Repo(cart))

    async def __aenter__(self):
        type(self).active += 1
        return self

    async def __aexit__(self, *args):
        type(self).active -= 1
        return None


def setup_checkout(
    accepted,
    extra_quantity=0,
    rejection_reason="Restaurant result is unknown",
    add_unordered_item=False,
):
    user = Obj(id=uuid4())
    restaurant = Obj(id=uuid4(), external_id="restaurant-1")
    branch = Obj(
        id=uuid4(),
        restaurant_id=restaurant.id,
        external_id="branch-1",
        is_active=True,
        is_accepting_orders=True,
    )
    menu_item = MenuItem(
        id=uuid4(),
        menu_id=uuid4(),
        external_id="item-1",
        name="Item",
        is_active=True,
    )
    cart = Cart(id=uuid4(), user_id=user.id, branch_id=branch.id, items=[])
    cart.add_item(menu_item, 2)
    item: CartItem = cart.items[0]
    other_menu_item = MenuItem(
        id=uuid4(),
        menu_id=menu_item.menu_id,
        external_id="item-2",
        name="Other",
    )
    relation = Obj(is_available=True, price=100)
    entered = []

    def factory():
        entered.append(len(entered) + 1)
        return FakeUow(user, branch, restaurant, cart, relation)

    class FakeOrderService:
        async def create_order(self, **kwargs):
            assert len(entered) == 1
            assert FakeUow.active == 0
            assert kwargs["request"].items[0].quantity == 2
            cart.update_item_quantity(
                menu_item.id, item.quantity + extra_quantity
            )
            if add_unordered_item:
                cart.add_item(other_menu_item, 4)
            if accepted:
                return Obj(
                    accepted=True,
                    order_id=uuid4(),
                    restaurant_order_id="remote-1",
                )
            return Obj(accepted=False, reason=Obj(message=rejection_reason))

    cart_service = CartService(factory)
    service = CheckoutService(cart_service, FakeOrderService(), factory)
    return service, cart, item, entered


@pytest.mark.asyncio
async def test_checkout_removes_only_ordered_quantities(monkeypatch):
    service, cart, item, entered = setup_checkout(True, extra_quantity=3)
    calls = []
    original = service.cart_service.remove_ordered_quantities

    async def tracked(*args):
        calls.append(1)
        await original(*args)

    monkeypatch.setattr(
        service.cart_service, "remove_ordered_quantities", tracked
    )
    response = await service.checkout(
        "user@example.com", uuid4(), CheckoutRequest(order_id="order-1")
    )
    assert response.accepted is True
    assert item.quantity == 3
    assert cart.items == [item]
    assert calls == [1]
    assert len(entered) == 2


@pytest.mark.asyncio
async def test_checkout_removes_fully_ordered_item():
    service, cart, _item, entered = setup_checkout(True)
    response = await service.checkout(
        "user@example.com", uuid4(), CheckoutRequest(order_id="order-1")
    )
    assert response.accepted is True
    assert cart.items == []
    assert len(entered) == 2


@pytest.mark.asyncio
async def test_checkout_keeps_item_added_after_order_request():
    service, cart, _item, entered = setup_checkout(
        True, add_unordered_item=True
    )
    response = await service.checkout(
        "user@example.com", uuid4(), CheckoutRequest(order_id="order-1")
    )
    assert response.accepted is True
    assert len(cart.items) == 1
    assert cart.items[0].menu_item.external_id == "item-2"
    assert cart.items[0].quantity == 4
    assert len(entered) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason", ["Restaurant rejected the order", "Restaurant result is unknown"]
)
async def test_checkout_preserves_cart_on_rejection_or_unknown_result(reason):
    service, cart, item, entered = setup_checkout(
        False, rejection_reason=reason
    )
    response = await service.checkout(
        "user@example.com", uuid4(), CheckoutRequest(order_id="order-1")
    )
    assert response.accepted is False
    assert response.reason == reason
    assert cart.items == [item] and item.quantity == 2
    assert len(entered) == 1
