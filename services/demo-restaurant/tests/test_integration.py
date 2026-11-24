from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SyncPayload
from app.service import DemoRestaurantService


class FakeKitchenClient:
    def __init__(self):
        self.payload = None

    async def sync_catalog(self, payload):
        self.payload = payload
        return {
            "status": "updated",
            "snapshot_id": payload["snapshot_id"],
        }


@pytest.mark.asyncio
async def test_sync_sends_current_contract(monkeypatch) -> None:
    client = FakeKitchenClient()
    service = DemoRestaurantService(None, client)
    payload = SyncPayload.model_validate(
        {
            "snapshot_id": uuid4(),
            "schema_version": 3,
            "catalog_revision": 7,
            "generated_at": datetime.now(UTC),
            "restaurant": {
                "external_id": "restaurant-1",
                "name": "Restaurant",
                "description": None,
            },
            "branches": [],
            "menu": {"external_id": "menu-1", "name": "Menu", "items": []},
            "availability": [],
        }
    )

    async def build_payload():
        return payload

    monkeypatch.setattr(service, "build_sync_payload", build_payload)
    response = await service.sync()
    assert response.status == "updated"
    assert client.payload["schema_version"] == 3
    assert client.payload["catalog_revision"] == 7
    assert all(
        "branch_version" not in branch
        for branch in client.payload["branches"]
    )


@pytest.mark.parametrize("schema_version", [1, 2])
def test_legacy_snapshot_is_rejected(schema_version: int) -> None:
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(
            {
                "snapshot_id": uuid4(),
                "schema_version": schema_version,
                "catalog_revision": 0,
                "generated_at": datetime.now(UTC),
                "restaurant": {
                    "external_id": "restaurant-1",
                    "name": "Restaurant",
                    "description": None,
                },
                "branches": [],
                "menu": {
                    "external_id": "menu-1",
                    "name": "Menu",
                    "items": [],
                },
                "availability": [],
            }
        )
