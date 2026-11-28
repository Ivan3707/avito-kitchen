from uuid import uuid4

import pytest

from app.infrastructure.clients.restaurant import RestaurantTimeoutError
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.orders.schemas import (
    BusinessErrorCode,
    CreateOrderRequest,
    RestaurantOrderResponse,
    ValidationIssue,
)
from app.modules.orders.service import OrderService
from app.modules.users.models.user import User

pytestmark = pytest.mark.integration


class FakeRestaurantClient:
    def __init__(self, response=None):
        self.calls = 0
        self.response = response or RestaurantOrderResponse(
            accepted=True,
            restaurant_order_id="restaurant-order-1",
        )

    async def create_order(self, payload):
        self.calls += 1
        return self.response


class TimeoutRestaurantClient:
    async def create_order(self, payload):
        raise RestaurantTimeoutError


async def create_catalog(
    session_factory,
    *,
    price: int | None = 100,
    is_available: bool = True,
):
    external_id = f"restaurant-{uuid4()}"
    branch_external_id = "branch-1"
    async with UnitOfWork(session_factory) as uow:
        user = await uow.users.users.get_by_email("customer@example.com")
        if user is None:
            uow.users.users.add(
                User(
                    email="customer@example.com",
                    password_hash="test-password-hash",
                )
            )
        restaurant = uow.catalog.restaurants.add(
            Restaurant(
                external_id=external_id,
                name="Restaurant",
                description=None,
            )
        )
        await uow.flush()
        branch = uow.catalog.restaurant_branches.add(
            RestaurantBranch(
                restaurant_id=restaurant.id,
                external_id=branch_external_id,
                name="Branch",
                address="Address",
                is_active=True,
                is_accepting_orders=True,
                branch_version=1,
            )
        )
        menu = uow.catalog.menus.add(
            Menu(
                restaurant_id=restaurant.id,
                external_id="menu-1",
                name="Menu",
            )
        )
        await uow.flush()
        item = uow.catalog.menu_items.add(
            MenuItem(
                menu_id=menu.id,
                external_id="item-1",
                name="Item",
                description=None,
                is_active=True,
            )
        )
        await uow.flush()
        uow.catalog.branch_menu_items.add(
            BranchMenuItem(
                branch_id=branch.id,
                menu_item_id=item.id,
                is_available=is_available,
                price=price,
            )
        )
    return external_id, branch_external_id


def request(restaurant_id, branch_id, *, order_id="order-1", price=100):
    return CreateOrderRequest(
        order_id=order_id,
        restaurant_external_id=restaurant_id,
        branch_external_id=branch_id,
        items=[
            {
                "menu_item_external_id": "item-1",
                "quantity": 1,
                "unit_price": price,
            }
        ],
    )


@pytest.mark.asyncio
async def test_create_order_and_retry_are_idempotent(test_session_factory):
    restaurant_id, branch_id = await create_catalog(test_session_factory)
    client = FakeRestaurantClient()
    service = OrderService()

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(test_session_factory)

    order_request = request(restaurant_id, branch_id)
    first = await service.create_order(
        uow_factory, order_request, "customer@example.com", client
    )
    second = await service.create_order(
        uow_factory, order_request, "customer@example.com", client
    )
    assert first.accepted is True
    assert second.restaurant_order_id == first.restaurant_order_id
    assert client.calls == 1


@pytest.mark.asyncio
async def test_same_order_id_with_other_payload_is_rejected(
    test_session_factory,
):
    restaurant_id, branch_id = await create_catalog(test_session_factory)
    client = FakeRestaurantClient()
    service = OrderService()

    def factory() -> UnitOfWork:
        return UnitOfWork(test_session_factory)

    await service.create_order(
        factory,
        request(restaurant_id, branch_id),
        "customer@example.com",
        client,
    )
    conflict = await service.create_order(
        factory,
        request(restaurant_id, branch_id, price=101),
        "customer@example.com",
        client,
    )
    assert conflict.accepted is False
    assert conflict.reason.code == BusinessErrorCode.ORDER_ID_CONFLICT


@pytest.mark.asyncio
async def test_restaurant_rejection_is_stored(test_session_factory):
    restaurant_id, branch_id = await create_catalog(test_session_factory)
    client = FakeRestaurantClient(
        RestaurantOrderResponse(
            accepted=False,
            reason=ValidationIssue(
                code=BusinessErrorCode.RESTAURANT_REJECTED,
                message="Rejected",
            ),
        )
    )
    service = OrderService()

    def factory() -> UnitOfWork:
        return UnitOfWork(test_session_factory)

    first = await service.create_order(
        factory,
        request(restaurant_id, branch_id),
        "customer@example.com",
        client,
    )
    retry = await service.create_order(
        factory,
        request(restaurant_id, branch_id),
        "customer@example.com",
        client,
    )
    assert first.accepted is False
    assert first.order_id is not None
    assert retry == first
    assert client.calls == 1


@pytest.mark.asyncio
async def test_timeout_leaves_recoverable_pending_order(test_session_factory):
    restaurant_id, branch_id = await create_catalog(test_session_factory)
    service = OrderService()

    def factory() -> UnitOfWork:
        return UnitOfWork(test_session_factory)

    timed_out = await service.create_order(
        factory,
        request(restaurant_id, branch_id),
        "customer@example.com",
        TimeoutRestaurantClient(),
    )
    recovered = await service.create_order(
        factory,
        request(restaurant_id, branch_id),
        "customer@example.com",
        FakeRestaurantClient(),
    )
    assert timed_out.reason.code == BusinessErrorCode.RESTAURANT_TIMEOUT
    assert recovered.accepted is True


@pytest.mark.asyncio
async def test_failed_local_finalize_commit_is_recoverable(
    test_session_factory,
):
    restaurant_id, branch_id = await create_catalog(test_session_factory)
    service = OrderService()
    client = FakeRestaurantClient()
    created = 0

    class FailingCommitUow(UnitOfWork):
        async def commit(self):
            raise RuntimeError("simulated local commit failure")

    def failing_factory():
        nonlocal created
        created += 1
        if created == 2:
            return FailingCommitUow(test_session_factory)
        return UnitOfWork(test_session_factory)

    with pytest.raises(RuntimeError, match="local commit failure"):
        await service.create_order(
            failing_factory,
            request(restaurant_id, branch_id),
            "customer@example.com",
            client,
        )

    recovered = await service.create_order(
        lambda: UnitOfWork(test_session_factory),
        request(restaurant_id, branch_id),
        "customer@example.com",
        client,
    )
    assert recovered.accepted is True


@pytest.mark.asyncio
async def test_catalog_rejection_avoids_restaurant_call(test_session_factory):
    restaurant_id, branch_id = await create_catalog(test_session_factory)
    client = FakeRestaurantClient()
    result = await OrderService().create_order(
        lambda: UnitOfWork(test_session_factory),
        request(restaurant_id, branch_id, price=101),
        "customer@example.com",
        client,
    )
    assert result.accepted is False
    assert result.reason.code == BusinessErrorCode.PRICE_CHANGED
    assert client.calls == 0


@pytest.mark.asyncio
async def test_item_without_branch_price_is_unavailable(
    test_session_factory,
):
    restaurant_id, branch_id = await create_catalog(
        test_session_factory,
        price=None,
        is_available=False,
    )
    client = FakeRestaurantClient()
    result = await OrderService().create_order(
        lambda: UnitOfWork(test_session_factory),
        request(restaurant_id, branch_id),
        "customer@example.com",
        client,
    )
    assert result.accepted is False
    assert result.reason.code == BusinessErrorCode.PRODUCT_UNAVAILABLE
    assert client.calls == 0
