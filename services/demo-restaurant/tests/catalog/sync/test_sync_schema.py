from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.catalog.sync.schemas import SyncPayload

pytestmark = pytest.mark.contract


def payload_data() -> dict:
    return {
        "snapshot_id": str(uuid4()),
        "schema_version": 3,
        "catalog_revision": 0,
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


def test_v3_contract_is_valid() -> None:
    payload = SyncPayload.model_validate(payload_data())
    assert payload.schema_version == 3
    assert payload.catalog_revision == 0


@pytest.mark.parametrize("schema_version", [1, 2])
def test_legacy_contract_is_rejected(schema_version: int) -> None:
    data = payload_data()
    data["schema_version"] = schema_version
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_branch_version_is_rejected() -> None:
    data = payload_data()
    data["branches"][0]["branch_version"] = 1
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


@pytest.mark.parametrize("revision", [-1, None])
def test_invalid_catalog_revision_is_rejected(revision) -> None:
    data = payload_data()
    if revision is None:
        del data["catalog_revision"]
    else:
        data["catalog_revision"] = revision
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_naive_generated_at_is_rejected() -> None:
    data = payload_data()
    data["generated_at"] = "2026-01-01T10:00:00"
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


@pytest.mark.parametrize("price", [0, -1, None])
def test_available_item_requires_positive_price(price) -> None:
    data = payload_data()
    data["availability"][0]["items"][0]["price"] = price
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_cross_references_must_be_complete() -> None:
    data = payload_data()
    data["availability"][0]["items"][0]["menu_item_external_id"] = (
        "unknown-item"
    )
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)


def test_duplicate_external_ids_are_rejected() -> None:
    data = payload_data()
    data["branches"].append(dict(data["branches"][0]))
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)

    data = payload_data()
    data["menu"]["items"].append(dict(data["menu"]["items"][0]))
    with pytest.raises(ValidationError):
        SyncPayload.model_validate(data)
