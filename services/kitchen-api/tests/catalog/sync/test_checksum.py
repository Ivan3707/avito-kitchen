from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.modules.catalog.sync.checksum import catalog_checksum
from app.modules.catalog.sync.schemas import SyncPayload

pytestmark = pytest.mark.unit

EXPECTED_DIGEST = (
    "4e3e28805cd5bccfc53326a114e24c99bf53e2241a9b859e613868c0be0df8ab"
)


def payload() -> SyncPayload:
    return SyncPayload.model_validate(
        {
            "snapshot_id": UUID("11111111-1111-1111-1111-111111111111"),
            "schema_version": 3,
            "catalog_revision": 4,
            "generated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "restaurant": {
                "external_id": "restaurant-1",
                "name": "Ресторан",
                "description": "Описание",
            },
            "branches": [
                {
                    "external_id": "branch-b",
                    "name": "Second",
                    "address": "B",
                    "is_active": True,
                    "is_accepting_orders": True,
                },
                {
                    "external_id": "branch-a",
                    "name": "First",
                    "address": "A",
                    "is_active": True,
                    "is_accepting_orders": True,
                },
            ],
            "menu": {
                "external_id": "menu-1",
                "name": "Меню",
                "items": [
                    {
                        "external_id": "item-b",
                        "name": "Tea",
                        "description": None,
                        "is_active": True,
                    },
                    {
                        "external_id": "item-a",
                        "name": "Coffee",
                        "description": "Hot",
                        "is_active": True,
                    },
                ],
            },
            "availability": [
                {
                    "branch_external_id": branch,
                    "items": [
                        {
                            "menu_item_external_id": item,
                            "is_available": True,
                            "price": price,
                        }
                        for item, price in (("item-b", 200), ("item-a", 100))
                    ],
                }
                for branch in ("branch-b", "branch-a")
            ],
        }
    )


def test_checksum_matches_contract_vector() -> None:
    assert catalog_checksum(payload()) == EXPECTED_DIGEST


def test_checksum_ignores_transport_metadata_and_array_order() -> None:
    original = payload()
    data = original.model_dump(mode="python")
    data["snapshot_id"] = UUID("22222222-2222-2222-2222-222222222222")
    data["catalog_revision"] = 99
    data["generated_at"] = datetime(2027, 2, 2, tzinfo=UTC)
    data["branches"].reverse()
    data["menu"]["items"].reverse()
    data["availability"].reverse()
    for entry in data["availability"]:
        entry["items"].reverse()
    variant = SyncPayload.model_validate(data).model_copy(
        update={"schema_version": 99}
    )
    assert catalog_checksum(variant) == catalog_checksum(original)


def test_checksum_changes_with_business_content() -> None:
    original = payload()
    original_digest = catalog_checksum(original)
    mutations = (
        ("restaurant", "name", "Other"),
        ("restaurant", "description", None),
        ("menu", "name", "Other menu"),
    )
    for section, field, value in mutations:
        data = original.model_dump(mode="python")
        data[section][field] = value
        assert catalog_checksum(SyncPayload.model_validate(data)) != (
            original_digest
        )

    for field, value in (("price", 101), ("is_available", False)):
        data = original.model_dump(mode="python")
        data["availability"][0]["items"][0][field] = value
        assert catalog_checksum(SyncPayload.model_validate(data)) != (
            original_digest
        )

    data = original.model_dump(mode="python")
    data["menu"]["items"][0]["is_active"] = False
    for entry in data["availability"]:
        entry["items"][0]["is_available"] = False
    assert (
        catalog_checksum(SyncPayload.model_validate(data)) != original_digest
    )
