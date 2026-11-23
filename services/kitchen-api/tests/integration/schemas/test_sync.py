from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.integration.schemas.sync import (
    IgnoredSyncResponse,
    SyncPayload,
    UpdatedSyncResponse,
)


def payload_data() -> dict:
    return {
        "snapshot_id": str(uuid4()),
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "restaurant": {
            "external_id": "restaurant-1",
            "name": "Restaurant",
            "description": None,
        },
        "branches": [
            {
                "external_id": "branch-1",
                "name": "Branch",
                "address": "Address",
                "is_active": True,
                "is_accepting_orders": True,
                "branch_version": 3,
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
                "branch_external_id": "branch-1",
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


def test_valid_sync_payload() -> None:
    payload = SyncPayload.model_validate(payload_data())
    assert payload.schema_version == 2
    assert payload.branches[0].branch_version == 3


def test_snapshot_allows_empty_restaurant_catalog() -> None:
    data = payload_data()
    data["branches"] = []
    data["menu"]["items"] = []
    data["availability"] = []
    SyncPayload.model_validate(data)


def test_generated_at_must_be_timezone_aware() -> None:
    data = payload_data()
    data["generated_at"] = "2026-01-01T10:00:00"
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_branch_version_must_be_positive() -> None:
    data = payload_data()
    data["branches"][0]["branch_version"] = 0
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_duplicate_branch_ids_are_rejected() -> None:
    data = payload_data()
    data["branches"].append(dict(data["branches"][0]))
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_availability_must_be_complete() -> None:
    data = payload_data()
    data["availability"][0]["items"] = []
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_inactive_branch_cannot_expose_available_item() -> None:
    data = payload_data()
    data["branches"][0]["is_active"] = False
    data["branches"][0]["is_accepting_orders"] = False
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_inactive_item_cannot_be_available() -> None:
    data = payload_data()
    data["menu"]["items"][0]["is_active"] = False
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_available_item_requires_price() -> None:
    data = payload_data()
    data["availability"][0]["items"][0]["price"] = None
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


@pytest.mark.parametrize("price", [0, -1])
def test_branch_price_must_be_positive(price: int) -> None:
    data = payload_data()
    data["availability"][0]["items"][0]["price"] = price
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_unavailable_item_allows_null_price() -> None:
    data = payload_data()
    data["availability"][0]["items"][0]["is_available"] = False
    data["availability"][0]["items"][0]["price"] = None
    payload = SyncPayload.model_validate(data)
    assert payload.availability[0].items[0].price is None


def test_availability_price_is_required() -> None:
    data = payload_data()
    del data["availability"][0]["items"][0]["price"]
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_v1_snapshot_is_rejected() -> None:
    data = payload_data()
    data["schema_version"] = 1
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_sync_responses_use_snapshot_identity() -> None:
    snapshot_id = uuid4()
    updated = UpdatedSyncResponse(snapshot_id=snapshot_id)
    ignored = IgnoredSyncResponse(
        snapshot_id=snapshot_id,
        reason="DUPLICATE_SNAPSHOT",
    )
    assert updated.status == "updated"
    assert ignored.status == "ignored"
