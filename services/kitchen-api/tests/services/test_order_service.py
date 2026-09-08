from uuid import uuid4

import pytest

from app.infrastructure.database.models.branch_menu_item import BranchMenuItem
from app.infrastructure.database.models.customer import Customer
from app.infrastructure.database.models.menu import Menu
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.common import BusinessErrorCode
from app.integration.schemas.orders import (
    CreateOrderRequest,
    OrderValidationRequest,
)
from app.services.order import OrderService


class FakeRestaurantClient:
    async def create_order(self, payload):
        return {
            "accepted": True,
            "restaurant_order_id": "restaurant-order-1",
        }


async def create_restaurant_structure(
    uow: UnitOfWork,
    *,
    branch_active: bool = True,
    branch_accepting_orders: bool = True,
    product_active: bool = True,
    product_available: bool = True,
    price: int = 500,
):
    restaurant = uow.restaurants.add(
        Restaurant(
            external_id=f"restaurant-{uuid4()}",
            name="Test Restaurant",
            description="Test description",
            sync_version=1,
        )
    )

    await uow.session.flush()

    branch = uow.restaurant_branches.add(
        RestaurantBranch(
            restaurant_id=restaurant.id,
            external_id=f"branch-{uuid4()}",
            name="Test Branch",
            address="Test address",
            is_active=branch_active,
            is_accepting_orders=branch_accepting_orders,
        )
    )

    menu = uow.menus.add(
        Menu(
            restaurant_id=restaurant.id,
            external_id=f"menu-{uuid4()}",
            name="Test Menu",
        )
    )

    await uow.session.flush()

    menu_item = uow.menu_items.add(
        MenuItem(
            menu_id=menu.id,
            external_id="burger",
            name="Burger",
            description="Test burger",
            price=price,
            is_active=product_active,
        )
    )

    await uow.session.flush()

    branch_menu_item = uow.branch_menu_items.add(
        BranchMenuItem(
            branch_id=branch.id,
            menu_item_id=menu_item.id,
            is_available=product_available,
        )
    )

    await uow.session.flush()

    return restaurant, branch, menu, menu_item, branch_menu_item


def validation_request(
    branch_external_id: str,
    *,
    menu_item_external_id: str = "burger",
    unit_price: int = 500,
    quantity: int = 1,
) -> OrderValidationRequest:
    return OrderValidationRequest(
        branch_external_id=branch_external_id,
        items=[
            {
                "menu_item_external_id": menu_item_external_id,
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
    )


def create_request(
    branch_external_id: str,
    *,
    order_id: str = "order-1",
    menu_item_external_id: str = "burger",
    unit_price: int = 500,
    quantity: int = 1,
) -> CreateOrderRequest:
    return CreateOrderRequest(
        order_id=order_id,
        branch_external_id=branch_external_id,
        items=[
            {
                "menu_item_external_id": menu_item_external_id,
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
    )


@pytest.mark.asyncio
async def test_validate_order_success(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(uow)

    service = OrderService()

    response = await service.validate_order(
        uow,
        validation_request(branch.external_id),
    )

    assert response.valid is True
    assert response.issues == []


@pytest.mark.asyncio
async def test_validate_order_branch_not_found(
    uow: UnitOfWork,
) -> None:
    service = OrderService()

    response = await service.validate_order(
        uow,
        validation_request("unknown-branch"),
    )

    assert response.valid is False
    assert len(response.issues) == 1
    assert response.issues[0].code == BusinessErrorCode.BRANCH_UNAVAILABLE


@pytest.mark.asyncio
async def test_validate_order_branch_unavailable(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(
        uow,
        branch_active=False,
        branch_accepting_orders=False,
    )

    service = OrderService()

    response = await service.validate_order(
        uow,
        validation_request(branch.external_id),
    )

    assert response.valid is False
    assert response.issues[0].code == BusinessErrorCode.BRANCH_UNAVAILABLE


@pytest.mark.asyncio
async def test_validate_order_product_not_found(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(uow)

    service = OrderService()

    response = await service.validate_order(
        uow,
        validation_request(
            branch.external_id,
            menu_item_external_id="unknown-product",
        ),
    )

    assert response.valid is False
    assert response.issues[0].code == BusinessErrorCode.PRODUCT_NOT_FOUND
    assert response.issues[0].menu_item_external_id == "unknown-product"


@pytest.mark.asyncio
async def test_validate_order_product_inactive(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(
        uow,
        product_active=False,
    )

    service = OrderService()

    response = await service.validate_order(
        uow,
        validation_request(branch.external_id),
    )

    assert response.valid is False
    assert response.issues[0].code == BusinessErrorCode.PRODUCT_UNAVAILABLE
    assert response.issues[0].menu_item_external_id == "burger"


@pytest.mark.asyncio
async def test_validate_order_product_unavailable_in_branch(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(
        uow,
        product_available=False,
    )

    service = OrderService()

    response = await service.validate_order(
        uow,
        validation_request(branch.external_id),
    )

    assert response.valid is False
    assert response.issues[0].code == BusinessErrorCode.PRODUCT_UNAVAILABLE


@pytest.mark.asyncio
async def test_validate_order_price_changed(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(
        uow,
        price=500,
    )

    service = OrderService()

    response = await service.validate_order(
        uow,
        validation_request(
            branch.external_id,
            unit_price=400,
        ),
    )

    assert response.valid is False

    issue = response.issues[0]

    assert issue.code == BusinessErrorCode.PRICE_CHANGED
    assert issue.old_price == 400
    assert issue.current_price == 500


@pytest.mark.asyncio
async def test_create_order_success(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(uow)

    service = OrderService()

    response = await service.create_order(
        uow,
        create_request(branch.external_id),
        customer_email="customer@example.com",
        restaurant_client=FakeRestaurantClient(),
    )

    assert response.accepted is True
    assert response.restaurant_order_id is not None
    assert response.reason is None

    customer = await uow.customers.get_by_email(
        "customer@example.com",
    )

    assert customer is not None

    order = await uow.orders.get_by_external_id(
        branch.restaurant_id,
        "order-1",
    )

    assert order is not None
    assert order.customer_id == customer.id
    assert order.branch_id == branch.id
    assert order.restaurant_order_id == response.restaurant_order_id
    assert order.request_hash


@pytest.mark.asyncio
async def test_create_order_rejects_invalid_order(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(uow)

    service = OrderService()

    response = await service.create_order(
        uow,
        create_request(
            branch.external_id,
            unit_price=400,
        ),
        customer_email="customer@example.com",
        restaurant_client=FakeRestaurantClient(),
    )

    assert response.accepted is False
    assert response.restaurant_order_id is None
    assert response.reason is not None
    assert response.reason.code == BusinessErrorCode.PRICE_CHANGED


@pytest.mark.asyncio
async def test_create_order_is_idempotent(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(uow)

    service = OrderService()

    request = create_request(
        branch.external_id,
        order_id="same-order",
    )

    first_response = await service.create_order(
        uow,
        request,
        customer_email="customer@example.com",
        restaurant_client=FakeRestaurantClient(),
    )

    second_response = await service.create_order(
        uow,
        request,
        customer_email="customer@example.com",
        restaurant_client=FakeRestaurantClient(),
    )

    assert first_response.accepted is True
    assert second_response.accepted is True

    assert (
        first_response.restaurant_order_id
        == second_response.restaurant_order_id
    )


@pytest.mark.asyncio
async def test_create_order_rejects_unknown_branch(
    uow: UnitOfWork,
) -> None:
    service = OrderService()

    response = await service.create_order(
        uow,
        create_request("unknown-branch"),
        customer_email="customer@example.com",
        restaurant_client=FakeRestaurantClient(),
    )

    assert response.accepted is False
    assert response.reason is not None
    assert response.reason.code == BusinessErrorCode.BRANCH_UNAVAILABLE


@pytest.mark.asyncio
async def test_create_order_reuses_existing_customer(
    uow: UnitOfWork,
) -> None:
    _, branch, _, _, _ = await create_restaurant_structure(uow)

    customer = uow.customers.add(
        Customer(
            email="existing@example.com",
        )
    )

    await uow.session.flush()

    service = OrderService()

    response = await service.create_order(
        uow,
        create_request(branch.external_id),
        customer_email=customer.email,
        restaurant_client=FakeRestaurantClient(),
    )

    assert response.accepted is True

    existing_customer = await uow.customers.get_by_email(
        "existing@example.com",
    )

    assert existing_customer is not None
    assert existing_customer.id == customer.id
