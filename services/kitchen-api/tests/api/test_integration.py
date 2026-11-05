from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.integration import get_uow, router
from app.infrastructure.clients.restaurant import RestaurantClient
from app.infrastructure.unit_of_work import UnitOfWork


@pytest.fixture
def api_app(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def override_get_uow() -> UnitOfWork:
        return UnitOfWork(test_session_factory)

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


def sync_payload(
    version: int = 1,
    *,
    branch_active: bool = True,
    branch_accepting_orders: bool = True,
    product_active: bool = True,
    product_available: bool = True,
    price: int = 500,
) -> dict:
    branch_external_id = f"branch-{uuid4()}"

    return {
        "version": version,
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
                "is_active": branch_active,
                "is_accepting_orders": branch_accepting_orders,
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
                    "price": price,
                    "is_active": product_active,
                }
            ],
        },
        "availability": [
            {
                "branch_external_id": branch_external_id,
                "items": [
                    {
                        "menu_item_external_id": "burger",
                        "is_available": product_available,
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_sync_endpoint_returns_updated(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/integration/v1/sync",
        json=sync_payload(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "updated"
    assert response.json()["version"] == 1


@pytest.mark.asyncio
async def test_sync_endpoint_ignores_outdated_version(
    client: AsyncClient,
) -> None:
    payload = sync_payload()

    first_response = await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    second_response = await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert second_response.json() == {
        "status": "ignored",
        "version": 1,
        "reason": "OUTDATED_VERSION",
    }


@pytest.mark.asyncio
async def test_validate_order_returns_valid(
    client: AsyncClient,
) -> None:
    payload = sync_payload()
    await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    response = await client.post(
        "/integration/v1/orders/validate",
        json={
            "branch_external_id": payload["branches"][0]["external_id"],
            "items": [
                {
                    "menu_item_external_id": "burger",
                    "quantity": 2,
                    "unit_price": 500,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "issues": [],
    }


@pytest.mark.asyncio
async def test_validate_order_returns_branch_unavailable(
    client: AsyncClient,
) -> None:
    payload = sync_payload(
        branch_active=False,
        branch_accepting_orders=False,
    )
    await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    response = await client.post(
        "/integration/v1/orders/validate",
        json={
            "branch_external_id": payload["branches"][0]["external_id"],
            "items": [
                {
                    "menu_item_external_id": "burger",
                    "quantity": 1,
                    "unit_price": 500,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["issues"][0]["code"] == "BRANCH_UNAVAILABLE"


@pytest.mark.asyncio
async def test_validate_order_returns_price_changed(
    client: AsyncClient,
) -> None:
    payload = sync_payload(price=500)
    await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    response = await client.post(
        "/integration/v1/orders/validate",
        json={
            "branch_external_id": payload["branches"][0]["external_id"],
            "items": [
                {
                    "menu_item_external_id": "burger",
                    "quantity": 1,
                    "unit_price": 400,
                }
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["valid"] is False
    assert body["issues"][0]["code"] == "PRICE_CHANGED"
    assert body["issues"][0]["old_price"] == 400
    assert body["issues"][0]["current_price"] == 500


@pytest.mark.asyncio
async def test_validate_order_returns_product_unavailable(
    client: AsyncClient,
) -> None:
    payload = sync_payload(
        product_available=False,
    )
    await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    response = await client.post(
        "/integration/v1/orders/validate",
        json={
            "branch_external_id": payload["branches"][0]["external_id"],
            "items": [
                {
                    "menu_item_external_id": "burger",
                    "quantity": 1,
                    "unit_price": 500,
                }
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["valid"] is False
    assert body["issues"][0]["code"] == "PRODUCT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_create_order_returns_accepted(
    client: AsyncClient, monkeypatch
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
    await client.post(
        "/integration/v1/sync",
        json=payload,
    )

    response = await client.post(
        "/integration/v1/orders",
        headers={
            "X-User-Email": "test@example.com",
        },
        json={
            "order_id": "order-1",
            "branch_external_id": payload["branches"][0]["external_id"],
            "items": [
                {
                    "menu_item_external_id": "burger",
                    "quantity": 2,
                    "unit_price": 500,
                }
            ],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["accepted"] is True
    assert body["restaurant_order_id"]
    assert body["reason"] is None


@pytest.mark.asyncio
async def test_create_order_is_idempotent(
    client: AsyncClient, monkeypatch
) -> None:
    sync_data = sync_payload()

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
    await client.post(
        "/integration/v1/sync",
        json=sync_data,
    )

    payload = {
        "order_id": "order-idempotent",
        "branch_external_id": sync_data["branches"][0]["external_id"],
        "items": [
            {
                "menu_item_external_id": "burger",
                "quantity": 2,
                "unit_price": 500,
            }
        ],
    }

    first_response = await client.post(
        "/integration/v1/orders",
        headers={"X-User-Email": "test@example.com"},
        json=payload,
    )

    second_response = await client.post(
        "/integration/v1/orders",
        headers={"X-User-Email": "test@example.com"},
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_order_id = first_response.json()["restaurant_order_id"]
    second_order_id = second_response.json()["restaurant_order_id"]

    assert first_order_id == second_order_id
