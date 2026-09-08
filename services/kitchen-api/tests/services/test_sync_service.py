from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.sync import (
    BranchAvailabilitySync,
    BranchSync,
    MenuItemAvailabilitySync,
    MenuItemSync,
    MenuSync,
    RestaurantSync,
    SyncPayload,
)
from app.services.sync import SyncService


def make_payload(
    *,
    version: int,
    restaurant_external_id: str,
    branch_external_id: str,
    menu_external_id: str,
    menu_item_external_id: str,
) -> SyncPayload:
    return SyncPayload(
        version=version,
        restaurant=RestaurantSync(
            external_id=restaurant_external_id,
            name="Test Restaurant",
            description="Test description",
        ),
        branches=[
            BranchSync(
                external_id=branch_external_id,
                name="Test Branch",
                address="Test address",
                is_active=True,
                is_accepting_orders=True,
            )
        ],
        menu=MenuSync(
            external_id=menu_external_id,
            name="Test Menu",
            items=[
                MenuItemSync(
                    external_id=menu_item_external_id,
                    name="Test Item",
                    description="Test item",
                    price=500,
                    is_active=True,
                )
            ],
        ),
        availability=[
            BranchAvailabilitySync(
                branch_external_id=branch_external_id,
                items=[
                    MenuItemAvailabilitySync(
                        menu_item_external_id=menu_item_external_id,
                        is_available=True,
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_sync_creates_full_restaurant_structure(
    uow: UnitOfWork,
) -> None:
    restaurant_external_id = f"restaurant-{uuid4()}"
    branch_external_id = f"branch-{uuid4()}"
    menu_external_id = f"menu-{uuid4()}"
    menu_item_external_id = f"item-{uuid4()}"

    payload = make_payload(
        version=1,
        restaurant_external_id=restaurant_external_id,
        branch_external_id=branch_external_id,
        menu_external_id=menu_external_id,
        menu_item_external_id=menu_item_external_id,
    )

    service = SyncService()

    response = await service.sync(
        uow=uow,
        payload=payload,
    )

    assert response.status == "updated"
    assert response.version == 1

    restaurant = await uow.restaurants.get_by_external_id(
        restaurant_external_id,
    )

    assert restaurant is not None
    assert restaurant.name == "Test Restaurant"
    assert restaurant.description == "Test description"
    assert restaurant.sync_version == 1

    branch = await uow.restaurant_branches.get_by_restaurant_and_external_id(
        restaurant.id,
        branch_external_id,
    )

    assert branch is not None
    assert branch.name == "Test Branch"
    assert branch.address == "Test address"
    assert branch.is_active is True
    assert branch.is_accepting_orders is True

    menu = await uow.menus.get_by_restaurant_id(
        restaurant.id,
    )

    assert menu is not None
    assert menu.external_id == menu_external_id
    assert menu.name == "Test Menu"

    menu_item = await uow.menu_items.get_by_menu_and_external_id(
        menu.id,
        menu_item_external_id,
    )

    assert menu_item is not None
    assert menu_item.name == "Test Item"
    assert menu_item.price == 500
    assert menu_item.is_active is True

    branch_menu_item = await uow.branch_menu_items.get_by_branch_and_menu_item(
        branch.id,
        menu_item.id,
    )

    assert branch_menu_item is not None
    assert branch_menu_item.is_available is True


@pytest.mark.asyncio
async def test_sync_ignores_outdated_version(
    uow: UnitOfWork,
) -> None:
    restaurant_external_id = f"restaurant-{uuid4()}"
    branch_external_id = f"branch-{uuid4()}"
    menu_external_id = f"menu-{uuid4()}"
    menu_item_external_id = f"item-{uuid4()}"

    service = SyncService()

    first_payload = make_payload(
        version=2,
        restaurant_external_id=restaurant_external_id,
        branch_external_id=branch_external_id,
        menu_external_id=menu_external_id,
        menu_item_external_id=menu_item_external_id,
    )

    first_response = await service.sync(
        uow=uow,
        payload=first_payload,
    )

    assert first_response.status == "updated"

    outdated_payload = make_payload(
        version=1,
        restaurant_external_id=restaurant_external_id,
        branch_external_id=branch_external_id,
        menu_external_id=menu_external_id,
        menu_item_external_id=menu_item_external_id,
    )

    outdated_payload.restaurant.name = "Changed Restaurant"

    response = await service.sync(
        uow=uow,
        payload=outdated_payload,
    )

    assert response.status == "ignored"
    assert response.version == 2

    restaurant = await uow.restaurants.get_by_external_id(
        restaurant_external_id,
    )

    assert restaurant is not None
    assert restaurant.name == "Test Restaurant"
    assert restaurant.sync_version == 2


@pytest.mark.asyncio
async def test_sync_updates_existing_restaurant(
    uow: UnitOfWork,
) -> None:
    restaurant_external_id = f"restaurant-{uuid4()}"
    branch_external_id = f"branch-{uuid4()}"
    menu_external_id = f"menu-{uuid4()}"
    menu_item_external_id = f"item-{uuid4()}"

    service = SyncService()

    first_payload = make_payload(
        version=1,
        restaurant_external_id=restaurant_external_id,
        branch_external_id=branch_external_id,
        menu_external_id=menu_external_id,
        menu_item_external_id=menu_item_external_id,
    )

    await service.sync(
        uow=uow,
        payload=first_payload,
    )

    updated_payload = make_payload(
        version=2,
        restaurant_external_id=restaurant_external_id,
        branch_external_id=branch_external_id,
        menu_external_id=menu_external_id,
        menu_item_external_id=menu_item_external_id,
    )

    updated_payload.restaurant.name = "Updated Restaurant"
    updated_payload.restaurant.description = "Updated description"

    response = await service.sync(
        uow=uow,
        payload=updated_payload,
    )

    assert response.status == "updated"
    assert response.version == 2

    restaurant = await uow.restaurants.get_by_external_id(
        restaurant_external_id,
    )

    assert restaurant is not None
    assert restaurant.name == "Updated Restaurant"
    assert restaurant.description == "Updated description"
    assert restaurant.sync_version == 2
