from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.cart import get_uow, router
from app.api.catalog import router as catalog_router
from app.api.integration import router as integration_router
from app.infrastructure.clients.restaurant import RestaurantClient
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture
def api_app(uow: UnitOfWork) -> FastAPI:
    app = FastAPI()

    app.include_router(router)
    app.include_router(catalog_router)
    app.include_router(integration_router)

    async def override_get_uow() -> UnitOfWork:
        return uow

    app.dependency_overrides[get_uow] = override_get_uow

    return app


@pytest_asyncio.fixture
async def client(api_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=api_app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


def sync_payload() -> dict:
    branch_external_id = f"branch-{uuid4()}"

    return {
        "version": 1,
        "restaurant": {
            "external_id": f"restaurant-{uuid4()}",
            "name": "Test Restaurant",
            "description": "Test description",
        },
        "branches": [
            {
                "external_id": branch_external_id,
                "name": "Test Branch",
                "address": "Test address",
                "is_active": True,
                "is_accepting_orders": True,
            }
        ],
        "menu": {
            "external_id": f"menu-{uuid4()}",
            "name": "Test Menu",
            "items": [
                {
                    "external_id": "burger",
                    "name": "Burger",
                    "description": "Test burger",
                    "price": 500,
                    "is_active": True,
                }
            ],
        },
        "availability": [
            {
                "branch_external_id": branch_external_id,
                "items": [
                    {
                        "menu_item_external_id": "burger",
                        "is_available": True,
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_checkout_accepts_order_and_clears_cart(
    client: AsyncClient,
    monkeypatch,
) -> None:
    payload = sync_payload()

    async def fake_create_order(self, payload):
        return {
            "accepted": True,
            "restaurant_order_id": "restaurant-order-1",
        }

    monkeypatch.setattr(
        RestaurantClient,
        "create_order",
        fake_create_order,
    )

    sync_response = await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    print(sync_response.json())

    restaurants_response = await client.get("/api/v1/restaurants")
    assert restaurants_response.status_code == 200
    print(restaurants_response.json())

    restaurant = next(
        restaurant
        for restaurant in restaurants_response.json()
        if (
            restaurant["name"] == payload["restaurant"]["name"]
            and restaurant["description"]
            == payload["restaurant"]["description"]
        )
    )

    restaurant_id = restaurant["id"]

    branches_response = await client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches"
    )
    assert branches_response.status_code == 200

    branch = next(
        branch
        for branch in branches_response.json()
        if (
            branch["name"] == payload["branches"][0]["name"]
            and branch["address"] == payload["branches"][0]["address"]
        )
    )

    branch_id = branch["id"]
    print("SELECTED RESTAURANT:", restaurant)
    print("BRANCHES:", branches_response.json())
    print("SELECTED BRANCH:", branch)
    print("BRANCH ID:", branch_id)

    # Получаем меню
    menu_response = await client.get(
        f"/api/v1/branches/{branch_id}/menu",
    )

    assert menu_response.status_code == 200

    menu_item_id = menu_response.json()["items"][0]["id"]

    # Добавляем товар в корзину
    add_response = await client.post(
        f"/api/v1/branches/{branch_id}/cart/items",
        headers={"X-User-Email": "checkout@example.com"},
        json={
            "menu_item_id": menu_item_id,
            "quantity": 2,
        },
    )

    assert add_response.status_code == 200
    assert len(add_response.json()["items"]) == 1

    await client.get(
        f"/api/v1/branches/{branch_id}/cart",
        headers={"X-User-Email": "empty@example.com"},
    )
    # Checkout
    checkout_response = await client.post(
        f"/api/v1/branches/{branch_id}/cart/checkout",
        headers={"X-User-Email": "checkout@example.com"},
        json={
            "order_id": "checkout-order-1",
        },
    )

    assert checkout_response.status_code == 200

    body = checkout_response.json()

    assert body["accepted"] is True
    assert body["restaurant_order_id"] == "restaurant-order-1"
    assert body["order_id"] is not None
    assert body["reason"] is None

    # Корзина должна быть очищена
    cart_response = await client.get(
        f"/api/v1/branches/{branch_id}/cart",
        headers={"X-User-Email": "checkout@example.com"},
    )

    assert cart_response.status_code == 200
    assert cart_response.json()["items"] == []


@pytest.mark.asyncio
async def test_checkout_rejected_keeps_cart(
    client: AsyncClient,
    monkeypatch,
) -> None:
    payload = sync_payload()

    async def fake_create_order(self, payload):
        return {
            "accepted": False,
            "reason": "Restaurant rejected the order",
        }

    monkeypatch.setattr(
        RestaurantClient,
        "create_order",
        fake_create_order,
    )

    await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    restaurants_response = await client.get(
        "/api/v1/restaurants",
    )

    restaurant = next(
        restaurant
        for restaurant in restaurants_response.json()
        if (
            restaurant["name"] == payload["restaurant"]["name"]
            and restaurant["description"]
            == payload["restaurant"]["description"]
        )
    )

    restaurant_id = restaurant["id"]

    branches_response = await client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches",
    )

    branch = next(
        branch
        for branch in branches_response.json()
        if (
            branch["name"] == payload["branches"][0]["name"]
            and branch["address"] == payload["branches"][0]["address"]
        )
    )

    branch_id = branch["id"]

    menu_response = await client.get(
        f"/api/v1/branches/{branch_id}/menu",
    )

    menu_item_id = menu_response.json()["items"][0]["id"]

    add_response = await client.post(
        f"/api/v1/branches/{branch_id}/cart/items",
        headers={"X-User-Email": "reject@example.com"},
        json={
            "menu_item_id": menu_item_id,
            "quantity": 2,
        },
    )

    assert add_response.status_code == 200

    checkout_response = await client.post(
        f"/api/v1/branches/{branch_id}/cart/checkout",
        headers={"X-User-Email": "reject@example.com"},
        json={
            "order_id": "checkout-rejected-1",
        },
    )

    assert checkout_response.status_code == 200

    body = checkout_response.json()

    assert body["accepted"] is False
    assert body["restaurant_order_id"] is None
    assert body["reason"] == "Restaurant rejected the order"

    # При REJECT корзина должна сохраниться
    cart_response = await client.get(
        f"/api/v1/branches/{branch_id}/cart",
        headers={"X-User-Email": "reject@example.com"},
    )

    assert cart_response.status_code == 200

    items = cart_response.json()["items"]

    assert len(items) == 1
    assert items[0]["quantity"] == 2


@pytest.mark.asyncio
async def test_checkout_empty_cart_does_not_call_restaurant(
    client: AsyncClient,
    monkeypatch,
) -> None:
    payload = sync_payload()

    await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    restaurants_response = await client.get(
        "/api/v1/restaurants",
    )

    restaurant_id = restaurants_response.json()[0]["id"]

    branches_response = await client.get(
        f"/api/v1/restaurants/{restaurant_id}/branches",
    )

    branch_id = branches_response.json()[0]["id"]

    called = False

    async def fake_create_order(self, payload):
        nonlocal called
        called = True
        return {
            "accepted": True,
            "restaurant_order_id": "restaurant-order-1",
        }

    monkeypatch.setattr(
        RestaurantClient,
        "create_order",
        fake_create_order,
    )
    await client.get(
        f"/api/v1/branches/{branch_id}/cart",
        headers={"X-User-Email": "empty@example.com"},
    )
    response = await client.post(
        f"/api/v1/branches/{branch_id}/cart/checkout",
        headers={"X-User-Email": "empty@example.com"},
        json={
            "order_id": "checkout-empty-1",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["accepted"] is False
    assert body["reason"] == "Cart is empty"
    assert called is False
