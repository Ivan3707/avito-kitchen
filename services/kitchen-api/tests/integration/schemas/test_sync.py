# pytest services/kitchen-api/tests/integration/schemas/test_sync.py -v
import pytest
from pydantic import ValidationError

from app.integration.schemas.sync import (
    BranchAvailabilitySync,
    BranchSync,
    IgnoredSyncResponse,
    MenuItemAvailabilitySync,
    MenuSync,
    RestaurantSync,
    SyncPayload,
    UpdatedSyncResponse,
)


def make_menu_items() -> list[dict]:
    return [
        {
            "external_id": "pizza-1",
            "name": "Pepperoni",
            "description": "Pizza with pepperoni",
            "price": 60000,
            "is_active": True,
        },
        {
            "external_id": "pizza-2",
            "name": "Margherita",
            "description": "Classic pizza",
            "price": 50000,
            "is_active": True,
        },
        {
            "external_id": "pizza-3",
            "name": "Hawaiian",
            "description": None,
            "price": 55000,
            "is_active": False,
        },
    ]


def make_branches() -> list[dict]:
    return [
        {
            "external_id": "branch-center",
            "name": "Demo Pizza — Центр",
            "address": "ул. Ленина, 10",
            "is_active": True,
            "is_accepting_orders": True,
        },
        {
            "external_id": "branch-north",
            "name": "Demo Pizza — Север",
            "address": "ул. Северная, 25",
            "is_active": True,
            "is_accepting_orders": False,
        },
    ]


def make_availability() -> list[dict]:
    return [
        {
            "branch_external_id": "branch-center",
            "items": [
                {
                    "menu_item_external_id": "pizza-1",
                    "is_available": True,
                },
                {
                    "menu_item_external_id": "pizza-2",
                    "is_available": False,
                },
                {
                    "menu_item_external_id": "pizza-3",
                    "is_available": True,
                },
            ],
        },
        {
            "branch_external_id": "branch-north",
            "items": [
                {
                    "menu_item_external_id": "pizza-1",
                    "is_available": False,
                },
                {
                    "menu_item_external_id": "pizza-2",
                    "is_available": True,
                },
                {
                    "menu_item_external_id": "pizza-3",
                    "is_available": False,
                },
            ],
        },
    ]


def make_sync_payload() -> dict:
    return {
        "version": 5,
        "restaurant": {
            "external_id": "demo-pizza",
            "name": "Demo Pizza",
            "description": "Пиццерия Demo Restaurant",
        },
        "branches": make_branches(),
        "menu": {
            "external_id": "main-menu",
            "name": "Основное меню",
            "items": make_menu_items(),
        },
        "availability": make_availability(),
    }


def test_valid_sync_payload() -> None:
    payload = SyncPayload.model_validate(make_sync_payload())

    assert payload.version == 5
    assert payload.restaurant.external_id == "demo-pizza"
    assert len(payload.branches) == 2
    assert len(payload.menu.items) == 3
    assert len(payload.availability) == 2


def test_valid_sync_payload_with_empty_menu() -> None:
    data = make_sync_payload()
    data["menu"]["items"] = []

    for branch_availability in data["availability"]:
        branch_availability["items"] = []

    payload = SyncPayload.model_validate(data)

    assert payload.menu.items == []
    assert all(
        availability.items == [] for availability in payload.availability
    )


def test_valid_sync_payload_with_inactive_branch() -> None:
    data = make_sync_payload()

    data["branches"][0]["is_active"] = False
    data["branches"][0]["is_accepting_orders"] = False

    payload = SyncPayload.model_validate(data)

    assert payload.branches[0].is_active is False
    assert payload.branches[0].is_accepting_orders is False


def test_valid_sync_payload_with_mixed_item_availability() -> None:
    payload = SyncPayload.model_validate(make_sync_payload())

    center = payload.availability[0]
    north = payload.availability[1]

    center_items = {
        item.menu_item_external_id: item.is_available for item in center.items
    }

    north_items = {
        item.menu_item_external_id: item.is_available for item in north.items
    }

    assert center_items == {
        "pizza-1": True,
        "pizza-2": False,
        "pizza-3": True,
    }

    assert north_items == {
        "pizza-1": False,
        "pizza-2": True,
        "pizza-3": False,
    }


def test_version_must_be_positive() -> None:
    data = make_sync_payload()
    data["version"] = 0

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        error["loc"] == ("version",) for error in exc_info.value.errors()
    )


def test_empty_external_id_is_invalid() -> None:
    data = make_sync_payload()
    data["restaurant"]["external_id"] = ""

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        error["loc"] == ("restaurant", "external_id")
        for error in exc_info.value.errors()
    )


def test_empty_branch_name_is_invalid() -> None:
    data = make_sync_payload()
    data["branches"][0]["name"] = ""

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        error["loc"] == ("branches", 0, "name")
        for error in exc_info.value.errors()
    )


def test_inactive_branch_cannot_accept_orders() -> None:
    data = make_sync_payload()

    data["branches"][0]["is_active"] = False
    data["branches"][0]["is_accepting_orders"] = True

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "inactive branch cannot accept orders" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_duplicate_branch_external_ids_are_invalid() -> None:
    data = make_sync_payload()
    data["branches"][1]["external_id"] = "branch-center"

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "branch external_id values must be unique" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_duplicate_menu_item_external_ids_are_invalid() -> None:
    data = make_sync_payload()
    data["menu"]["items"][1]["external_id"] = "pizza-1"

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "menu item external_id values must be unique" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_duplicate_availability_item_external_ids_are_invalid() -> None:
    data = make_sync_payload()

    data["availability"][0]["items"][1]["menu_item_external_id"] = "pizza-1"

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "menu item external_id values must be unique "
        "within branch availability" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_duplicate_availability_branch_entries_are_invalid() -> None:
    data = make_sync_payload()

    data["availability"][1]["branch_external_id"] = "branch-center"

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "each branch must have exactly one availability entry" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_missing_branch_from_availability_is_invalid() -> None:
    data = make_sync_payload()

    data["availability"].pop()

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "availability must contain every branch exactly once" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_unknown_branch_in_availability_is_invalid() -> None:
    data = make_sync_payload()

    data["availability"][0]["branch_external_id"] = "branch-unknown"

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "availability must contain every branch exactly once" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_missing_menu_item_from_availability_is_invalid() -> None:
    data = make_sync_payload()

    data["availability"][0]["items"].pop()

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "availability must contain every menu item "
        "for every branch exactly once" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_unknown_menu_item_in_availability_is_invalid() -> None:
    data = make_sync_payload()

    data["availability"][0]["items"][0]["menu_item_external_id"] = (
        "pizza-unknown"
    )

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "availability must contain every menu item "
        "for every branch exactly once" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_duplicate_branch_availability_items_are_invalid() -> None:
    data = make_sync_payload()

    data["availability"][0]["items"].append(
        {
            "menu_item_external_id": "pizza-1",
            "is_available": False,
        }
    )

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        "menu item external_id values must be unique "
        "within branch availability" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_empty_menu_item_external_id_is_invalid() -> None:
    data = make_sync_payload()
    data["menu"]["items"][0]["external_id"] = ""

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        error["loc"] == ("menu", "items", 0, "external_id")
        for error in exc_info.value.errors()
    )


def test_zero_menu_item_price_is_invalid() -> None:
    data = make_sync_payload()
    data["menu"]["items"][0]["price"] = 0

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        error["loc"] == ("menu", "items", 0, "price")
        for error in exc_info.value.errors()
    )


def test_negative_menu_item_price_is_invalid() -> None:
    data = make_sync_payload()
    data["menu"]["items"][0]["price"] = -100

    with pytest.raises(ValidationError) as exc_info:
        SyncPayload.model_validate(data)

    assert any(
        error["loc"] == ("menu", "items", 0, "price")
        for error in exc_info.value.errors()
    )


def test_valid_updated_sync_response() -> None:
    response = UpdatedSyncResponse(version=5)

    assert response.status == "updated"
    assert response.version == 5


def test_valid_ignored_sync_response() -> None:
    response = IgnoredSyncResponse(version=4)

    assert response.status == "ignored"
    assert response.version == 4
    assert response.reason == "OUTDATED_VERSION"


def test_updated_sync_response_requires_positive_version() -> None:
    with pytest.raises(ValidationError) as exc_info:
        UpdatedSyncResponse(version=0)

    assert any(
        error["loc"] == ("version",) for error in exc_info.value.errors()
    )


def test_ignored_sync_response_requires_positive_version() -> None:
    with pytest.raises(ValidationError) as exc_info:
        IgnoredSyncResponse(version=0)

    assert any(
        error["loc"] == ("version",) for error in exc_info.value.errors()
    )


def test_branch_sync_rejects_empty_external_id() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BranchSync(
            external_id="",
            name="Center",
            address="Address",
            is_active=True,
            is_accepting_orders=True,
        )

    assert any(
        error["loc"] == ("external_id",) for error in exc_info.value.errors()
    )


def test_menu_sync_rejects_duplicate_items() -> None:
    item = {
        "external_id": "pizza-1",
        "name": "Pepperoni",
        "description": None,
        "price": 60000,
        "is_active": True,
    }

    with pytest.raises(ValidationError) as exc_info:
        MenuSync(
            external_id="menu-1",
            name="Main menu",
            items=[item, item],
        )

    assert any(
        "menu item external_id values must be unique" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_branch_availability_rejects_duplicate_items() -> None:
    item = MenuItemAvailabilitySync(
        menu_item_external_id="pizza-1",
        is_available=True,
    )

    with pytest.raises(ValidationError) as exc_info:
        BranchAvailabilitySync(
            branch_external_id="branch-1",
            items=[item, item],
        )

    assert any(
        "menu item external_id values must be unique "
        "within branch availability" in error["msg"]
        for error in exc_info.value.errors()
    )


def test_restaurant_sync_accepts_null_description() -> None:
    restaurant = RestaurantSync(
        external_id="restaurant-1",
        name="Demo Restaurant",
        description=None,
    )

    assert restaurant.description is None
