import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.sync import SyncPayload
from app.services.sync import SyncService


def make_payload(
    *,
    restaurant_external_id: str,
    generated_at: datetime,
    snapshot_id=None,
    branch_version: int = 1,
    include_branch: bool = True,
    branch_active: bool = True,
) -> SyncPayload:
    branch_id = "branch-1"
    item_id = "item-1"
    return SyncPayload.model_validate(
        {
            "snapshot_id": snapshot_id or uuid4(),
            "schema_version": 2,
            "generated_at": generated_at,
            "restaurant": {
                "external_id": restaurant_external_id,
                "name": "Restaurant",
                "description": None,
            },
            "branches": (
                [
                    {
                        "external_id": branch_id,
                        "name": "Branch",
                        "address": "Address",
                        "is_active": branch_active,
                        "is_accepting_orders": branch_active,
                        "branch_version": branch_version,
                    }
                ]
                if include_branch
                else []
            ),
            "menu": {
                "external_id": "menu-1",
                "name": "Menu",
                "items": [
                    {
                        "external_id": item_id,
                        "name": "Item",
                        "description": None,
                        "is_active": True,
                    }
                ],
            },
            "availability": (
                [
                    {
                        "branch_external_id": branch_id,
                        "items": [
                            {
                                "menu_item_external_id": item_id,
                                "is_available": branch_active,
                                "price": 100,
                            }
                        ],
                    }
                ]
                if include_branch
                else []
            ),
        }
    )


@pytest.mark.asyncio
async def test_full_sync_and_duplicate_snapshot(uow: UnitOfWork) -> None:
    external_id = f"restaurant-{uuid4()}"
    payload = make_payload(
        restaurant_external_id=external_id,
        generated_at=datetime.now(UTC),
    )
    service = SyncService()
    first = await service.sync(uow, payload)
    duplicate = await service.sync(uow, payload)
    assert first.status == "updated"
    assert duplicate.status == "ignored"
    assert duplicate.reason == "DUPLICATE_SNAPSHOT"


@pytest.mark.asyncio
async def test_stale_snapshot_does_not_overwrite_newer(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    now = datetime.now(UTC)
    service = SyncService()
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now,
            branch_version=2,
        ),
    )
    stale = await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now - timedelta(seconds=1),
            branch_version=1,
        ),
    )
    assert stale.status == "ignored"
    assert stale.reason == "STALE_SNAPSHOT"


@pytest.mark.asyncio
async def test_branch_version_cannot_regress(uow: UnitOfWork) -> None:
    external_id = f"restaurant-{uuid4()}"
    now = datetime.now(UTC)
    service = SyncService()
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now,
            branch_version=4,
        ),
    )
    stale = await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now + timedelta(seconds=1),
            branch_version=3,
        ),
    )
    assert stale.status == "ignored"


@pytest.mark.asyncio
async def test_missing_branch_is_deactivated(uow: UnitOfWork) -> None:
    external_id = f"restaurant-{uuid4()}"
    now = datetime.now(UTC)
    service = SyncService()
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now,
        ),
    )
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now + timedelta(seconds=1),
            include_branch=False,
        ),
    )
    restaurant = await uow.restaurants.get_by_external_id(external_id)
    branches = await uow.restaurant_branches.get_by_restaurant_id(
        restaurant.id
    )
    relations = await uow.branch_menu_items.get_all_by_branch(branches[0].id)
    assert branches[0].is_active is False
    assert all(not relation.is_available for relation in relations)


@pytest.mark.asyncio
async def test_explicitly_deactivated_branch_disables_availability(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    now = datetime.now(UTC)
    service = SyncService()
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now,
        ),
    )
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            generated_at=now + timedelta(seconds=1),
            branch_version=2,
            branch_active=False,
        ),
    )
    restaurant = await uow.restaurants.get_by_external_id(external_id)
    branches = await uow.restaurant_branches.get_by_restaurant_id(
        restaurant.id
    )
    relations = await uow.branch_menu_items.get_all_by_branch(branches[0].id)
    assert branches[0].is_active is False
    assert branches[0].is_accepting_orders is False
    assert all(not relation.is_available for relation in relations)


@pytest.mark.asyncio
async def test_concurrent_snapshots_leave_newest_state(
    test_session_factory,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    now = datetime.now(UTC)
    service = SyncService()

    async def apply(payload):
        async with UnitOfWork(test_session_factory) as local_uow:
            return await service.sync(local_uow, payload)

    await asyncio.gather(
        apply(
            make_payload(
                restaurant_external_id=external_id,
                generated_at=now,
                branch_version=1,
            )
        ),
        apply(
            make_payload(
                restaurant_external_id=external_id,
                generated_at=now + timedelta(seconds=1),
                branch_version=2,
            )
        ),
    )
    async with UnitOfWork(test_session_factory) as check_uow:
        restaurant = await check_uow.restaurants.get_by_external_id(
            external_id
        )
        branches = await check_uow.restaurant_branches.get_by_restaurant_id(
            restaurant.id
        )
        assert branches[0].branch_version == 2


@pytest.mark.asyncio
async def test_sync_rolls_back_on_error(test_session_factory) -> None:
    external_id = f"restaurant-{uuid4()}"
    payload = make_payload(
        restaurant_external_id=external_id,
        generated_at=datetime.now(UTC),
    )
    with pytest.raises(RuntimeError):
        async with UnitOfWork(test_session_factory) as local_uow:
            await SyncService().sync(local_uow, payload)
            raise RuntimeError("fail after synchronization")
    async with UnitOfWork(test_session_factory) as check_uow:
        assert (
            await check_uow.restaurants.get_by_external_id(external_id) is None
        )


@pytest.mark.asyncio
async def test_sync_stores_different_prices_for_two_branches(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    data = make_payload(
        restaurant_external_id=external_id,
        generated_at=datetime.now(UTC),
    ).model_dump(mode="json")
    second_branch = dict(data["branches"][0])
    second_branch["external_id"] = "branch-2"
    data["branches"].append(second_branch)
    data["availability"].append(
        {
            "branch_external_id": "branch-2",
            "items": [
                {
                    "menu_item_external_id": "item-1",
                    "is_available": True,
                    "price": 175,
                }
            ],
        }
    )

    await SyncService().sync(uow, SyncPayload.model_validate(data))

    restaurant = await uow.restaurants.get_by_external_id(external_id)
    branches = await uow.restaurant_branches.get_by_restaurant_id(
        restaurant.id
    )
    relations = {
        branch.external_id: (
            await uow.branch_menu_items.get_all_by_branch(branch.id)
        )[0]
        for branch in branches
    }
    assert relations["branch-1"].price == 100
    assert relations["branch-2"].price == 175
