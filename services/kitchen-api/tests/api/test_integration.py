from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.integration import get_uow, get_uow_factory, router
from app.infrastructure.clients.restaurant import RestaurantClient
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.orders import RestaurantOrderResponse
from app.main import handle_conflict
from app.services.errors import ConflictError


@pytest.fixture
def api_app(test_session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(ConflictError, handle_conflict)
    app.dependency_overrides[get_uow] = lambda: UnitOfWork(
        test_session_factory
    )
    app.dependency_overrides[get_uow_factory] = lambda: (
        lambda: UnitOfWork(test_session_factory)
    )
    return app


@pytest_asyncio.fixture
async def client(api_app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=api_app), base_url="http://test"
    ) as http_client:
        yield http_client


def sync_payload(*, snapshot_id=None, generated_at=None, revision=0):
    restaurant_id = f"restaurant-{uuid4()}"
    branch_id = f"branch-{uuid4()}"
    return {
        "snapshot_id": str(snapshot_id or uuid4()),
        "schema_version": 3,
        "catalog_revision": revision,
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "restaurant": {
            "external_id": restaurant_id,
            "name": "Restaurant",
            "description": None,
        },
        "branches": [
            {
                "external_id": branch_id,
                "name": "Branch",
                "address": "Address",
                "is_active": True,
                "is_accepting_orders": True,
            }
        ],
        "menu": {
            "external_id": "menu-1",
            "name": "Menu",
            "items": [
                {
                    "external_id": "item-1",
                    "name": "Item",
                    "description": None,
                    "is_active": True,
                }
            ],
        },
        "availability": [
            {
                "branch_external_id": branch_id,
                "items": [
                    {
                        "menu_item_external_id": "item-1",
                        "is_available": True,
                        "price": 100,
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_sync_endpoint_updates_and_deduplicates(client):
    payload = sync_payload()
    first = await client.post("/integration/v1/sync", json=payload)
    duplicate = await client.post("/integration/v1/sync", json=payload)
    assert first.status_code == 200
    assert first.json()["snapshot_id"] == payload["snapshot_id"]
    assert duplicate.json()["reason"] == "DUPLICATE_SNAPSHOT"


@pytest.mark.asyncio
async def test_sync_endpoint_rejects_v2(client):
    payload = sync_payload()
    payload["schema_version"] = 2
    response = await client.post("/integration/v1/sync", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_endpoint_reports_integrity_conflict(client):
    payload = sync_payload(revision=1)
    first = await client.post("/integration/v1/sync", json=payload)
    conflicting = dict(payload)
    conflicting["snapshot_id"] = str(uuid4())
    conflicting["restaurant"] = dict(payload["restaurant"])
    conflicting["restaurant"]["name"] = "Other name"
    response = await client.post(
        "/integration/v1/sync",
        json=conflicting,
    )
    assert first.status_code == 200
    assert response.status_code == 409
    assert "different business content" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_order_contract(client, monkeypatch):
    payload = sync_payload()
    await client.post("/integration/v1/sync", json=payload)

    async def fake_create_order(self, request_payload):
        return RestaurantOrderResponse(
            accepted=True,
            restaurant_order_id="restaurant-order-1",
        )

    monkeypatch.setattr(RestaurantClient, "create_order", fake_create_order)
    response = await client.post(
        "/integration/v1/orders",
        headers={"X-User-Email": "customer@example.com"},
        json={
            "order_id": "order-1",
            "restaurant_external_id": payload["restaurant"]["external_id"],
            "branch_external_id": payload["branches"][0]["external_id"],
            "items": [
                {
                    "menu_item_external_id": "item-1",
                    "quantity": 1,
                    "unit_price": 100,
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is True
