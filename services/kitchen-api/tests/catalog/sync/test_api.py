from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_sync_service
from app.core.errors import ConflictError
from app.infrastructure.unit_of_work import UnitOfWork
from app.main import handle_conflict
from app.modules.catalog.sync.router import router as sync_router
from app.modules.catalog.sync.service import SyncService

pytestmark = pytest.mark.integration


@pytest.fixture
def api_app(test_session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(sync_router)
    app.add_exception_handler(ConflictError, handle_conflict)

    def factory():
        return UnitOfWork(test_session_factory)

    app.state.sync_service = SyncService(factory)

    app.dependency_overrides[get_sync_service] = lambda: app.state.sync_service
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
