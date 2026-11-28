import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.errors import ConflictError
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.sync.schemas import SyncPayload
from app.modules.catalog.sync.service import SyncService
from app.modules.orders.models.order import Order
from app.modules.orders.models.order_item import OrderItem, OrderItemSnapshot
from app.modules.users.models.user import User

pytestmark = pytest.mark.integration


def make_payload(
    *,
    restaurant_external_id: str,
    revision: int,
    snapshot_id: UUID | None = None,
    generated_at: datetime | None = None,
    branch_name: str = "Branch",
    item_name: str = "Item",
    include_catalog: bool = True,
    available: bool = True,
    price: int | None = 100,
) -> SyncPayload:
    branch_id = "branch-1"
    item_id = "item-1"
    return SyncPayload.model_validate(
        {
            "snapshot_id": snapshot_id or uuid4(),
            "schema_version": 3,
            "catalog_revision": revision,
            "generated_at": generated_at or datetime.now(UTC),
            "restaurant": {
                "external_id": restaurant_external_id,
                "name": "Restaurant",
                "description": None,
            },
            "branches": (
                [
                    {
                        "external_id": branch_id,
                        "name": branch_name,
                        "address": "Address",
                        "is_active": True,
                        "is_accepting_orders": True,
                    }
                ]
                if include_catalog
                else []
            ),
            "menu": {
                "external_id": "menu-1",
                "name": "Menu",
                "items": (
                    [
                        {
                            "external_id": item_id,
                            "name": item_name,
                            "description": None,
                            "is_active": True,
                        }
                    ]
                    if include_catalog
                    else []
                ),
            },
            "availability": (
                [
                    {
                        "branch_external_id": branch_id,
                        "items": [
                            {
                                "menu_item_external_id": item_id,
                                "is_available": available,
                                "price": price,
                            }
                        ],
                    }
                ]
                if include_catalog
                else []
            ),
        }
    )


@pytest.mark.asyncio
async def test_first_sync_and_exact_duplicate(uow: UnitOfWork) -> None:
    external_id = f"restaurant-{uuid4()}"
    payload = make_payload(restaurant_external_id=external_id, revision=0)
    first = await SyncService(lambda: UnitOfWork(uow.session_factory)).sync(
        uow, payload
    )
    duplicate = await SyncService(
        lambda: UnitOfWork(uow.session_factory)
    ).sync(uow, payload)
    assert first.status == "updated"
    assert duplicate.status == "ignored"
    assert duplicate.reason == "DUPLICATE_SNAPSHOT"


@pytest.mark.asyncio
async def test_revision_orders_snapshots_and_allows_gaps(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    now = datetime.now(UTC)
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=1,
            generated_at=now,
        ),
    )
    updated = await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=5,
            generated_at=now - timedelta(days=1),
            branch_name="Revision five",
        ),
    )
    stale = await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=3,
            generated_at=now + timedelta(days=1),
            branch_name="Stale",
        ),
    )
    restaurant = await uow.catalog.restaurants.get_by_external_id(external_id)
    branches = await uow.catalog.restaurant_branches.get_by_restaurant_id(
        restaurant.id
    )
    assert updated.status == "updated"
    assert stale.status == "ignored"
    assert stale.reason == "STALE_SNAPSHOT"
    assert restaurant.catalog_revision == 5
    assert branches[0].name == "Revision five"


@pytest.mark.asyncio
async def test_same_revision_and_checksum_is_duplicate_state(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(restaurant_external_id=external_id, revision=2),
    )
    repeated_state = await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=2,
            generated_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    assert repeated_state.status == "ignored"
    assert repeated_state.reason == "DUPLICATE_STATE"


@pytest.mark.asyncio
async def test_new_revision_with_same_checksum_is_processed(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(restaurant_external_id=external_id, revision=1),
    )
    response = await service.sync(
        uow,
        make_payload(restaurant_external_id=external_id, revision=2),
    )
    restaurant = await uow.catalog.restaurants.get_by_external_id(external_id)
    assert response.status == "updated"
    assert restaurant.catalog_revision == 2


@pytest.mark.asyncio
async def test_same_revision_with_different_content_conflicts(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(restaurant_external_id=external_id, revision=1),
    )
    with pytest.raises(ConflictError):
        await service.sync(
            uow,
            make_payload(
                restaurant_external_id=external_id,
                revision=1,
                branch_name="Conflicting",
            ),
        )
    restaurant = await uow.catalog.restaurants.get_by_external_id(external_id)
    branches = await uow.catalog.restaurant_branches.get_by_restaurant_id(
        restaurant.id
    )
    assert restaurant.catalog_revision == 1
    assert branches[0].name == "Branch"


@pytest.mark.asyncio
async def test_snapshot_id_reuse_with_other_content_conflicts(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    snapshot_id = uuid4()
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=1,
            snapshot_id=snapshot_id,
        ),
    )
    with pytest.raises(ConflictError):
        await service.sync(
            uow,
            make_payload(
                restaurant_external_id=external_id,
                revision=2,
                snapshot_id=snapshot_id,
            ),
        )


@pytest.mark.asyncio
async def test_snapshot_id_reuse_by_other_restaurant_conflicts(
    uow: UnitOfWork,
) -> None:
    snapshot_id = uuid4()
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=f"restaurant-{uuid4()}",
            revision=1,
            snapshot_id=snapshot_id,
        ),
    )
    with pytest.raises(ConflictError):
        await service.sync(
            uow,
            make_payload(
                restaurant_external_id=f"restaurant-{uuid4()}",
                revision=1,
                snapshot_id=snapshot_id,
            ),
        )


@pytest.mark.asyncio
async def test_legacy_restaurant_accepts_revision_zero(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    legacy = uow.catalog.restaurants.add(
        Restaurant(
            external_id=external_id,
            name="Legacy",
            description=None,
        )
    )
    await uow.flush()
    response = await SyncService(lambda: UnitOfWork(uow.session_factory)).sync(
        uow,
        make_payload(restaurant_external_id=external_id, revision=0),
    )
    assert response.status == "updated"
    assert legacy.catalog_revision == 0
    assert legacy.catalog_checksum is not None


@pytest.mark.asyncio
async def test_full_snapshot_deactivates_missing_catalog(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(restaurant_external_id=external_id, revision=1),
    )
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=2,
            include_catalog=False,
        ),
    )
    restaurant = await uow.catalog.restaurants.get_by_external_id(external_id)
    branch = (
        await uow.catalog.restaurant_branches.get_by_restaurant_id(
            restaurant.id
        )
    )[0]
    menu = await uow.catalog.menus.get_by_restaurant_id(restaurant.id)
    item = (await uow.catalog.menu_items.get_by_menu_id(menu.id))[0]
    relation = (
        await uow.catalog.branch_menu_items.get_all_by_branch(branch.id)
    )[0]
    assert branch.is_active is False
    assert branch.is_accepting_orders is False
    assert item.is_active is False
    assert relation.is_available is False
    assert relation.price is None


@pytest.mark.asyncio
async def test_full_snapshot_preserves_historical_order_references(
    uow: UnitOfWork,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    await service.sync(
        uow,
        make_payload(restaurant_external_id=external_id, revision=1),
    )
    restaurant = await uow.catalog.restaurants.get_by_external_id(external_id)
    branch = (
        await uow.catalog.restaurant_branches.get_by_restaurant_id(
            restaurant.id
        )
    )[0]
    menu = await uow.catalog.menus.get_by_restaurant_id(restaurant.id)
    item = (await uow.catalog.menu_items.get_by_menu_id(menu.id))[0]
    user = uow.users.users.add(
        User(
            email=f"{uuid4()}@example.com",
            password_hash="test-password-hash",
        )
    )
    await uow.flush()
    historical_name = item.name
    order = Order.create_pending(
        user_id=user.id,
        restaurant_id=restaurant.id,
        branch_id=branch.id,
        external_order_id=str(uuid4()),
        request_hash="hash",
        items=[
            OrderItemSnapshot(
                menu_item_id=item.id,
                product_name=historical_name,
                unit_price=100,
                quantity=1,
            )
        ],
    )
    order.confirm("restaurant-order-1")
    uow.orders.orders.add(order)
    await uow.flush()
    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=2,
            include_catalog=False,
        ),
    )
    assert await uow.orders.orders.get_by_id(order.id) is order
    stored_items = await uow.session.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    stored_item = stored_items.one()
    assert stored_item.menu_item_id == item.id
    assert (
        stored_item.product_name,
        stored_item.unit_price,
        stored_item.quantity,
    ) == (
        historical_name,
        100,
        1,
    )

    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=external_id,
            revision=3,
            item_name="Renamed in catalog",
            price=125,
        ),
    )
    current_item = await uow.catalog.menu_items.get_by_id(item.id)
    current_price = (
        await uow.catalog.branch_menu_items.get_by_branch_and_menu_item(
            branch.id, item.id
        )
    )
    assert current_item.name == "Renamed in catalog"
    assert current_price.price == 125
    stored_item = (
        await uow.session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
    ).one()
    assert (
        stored_item.product_name,
        stored_item.unit_price,
        stored_item.quantity,
    ) == (historical_name, 100, 1)


@pytest.mark.asyncio
async def test_history_is_recorded_and_cleaned_per_restaurant(
    uow: UnitOfWork,
) -> None:
    first_external_id = f"restaurant-{uuid4()}"
    second_external_id = f"restaurant-{uuid4()}"
    service = SyncService(lambda: UnitOfWork(uow.session_factory))
    first_payload = make_payload(
        restaurant_external_id=first_external_id,
        revision=1,
    )
    second_payload = make_payload(
        restaurant_external_id=second_external_id,
        revision=1,
    )
    await service.sync(uow, first_payload)
    await service.sync(uow, second_payload)
    first_history = await uow.catalog.sync_snapshots.get_by_id(
        first_payload.snapshot_id
    )
    second_history = await uow.catalog.sync_snapshots.get_by_id(
        second_payload.snapshot_id
    )
    assert first_history.catalog_revision == 1
    assert len(first_history.catalog_checksum) == 64
    assert first_history.processed_at is not None
    old_time = datetime.now(UTC) - timedelta(days=31)
    first_history.processed_at = old_time
    second_history.processed_at = old_time
    await uow.flush()

    await service.sync(
        uow,
        make_payload(
            restaurant_external_id=first_external_id,
            revision=2,
        ),
    )
    assert (
        await uow.catalog.sync_snapshots.get_by_id(first_payload.snapshot_id)
        is None
    )
    assert (
        await uow.catalog.sync_snapshots.get_by_id(second_payload.snapshot_id)
        is not None
    )
    current = await uow.catalog.restaurants.get_by_external_id(
        first_external_id
    )
    assert current.catalog_revision == 2
    assert current.catalog_checksum is not None
    replay = await service.sync(uow, first_payload)
    assert replay.status == "ignored"
    assert replay.reason == "STALE_SNAPSHOT"
    assert current.catalog_revision == 2


@pytest.mark.asyncio
async def test_sync_rolls_back_on_error(test_session_factory) -> None:
    external_id = f"restaurant-{uuid4()}"
    payload = make_payload(restaurant_external_id=external_id, revision=0)
    with pytest.raises(RuntimeError, match="fail after synchronization"):
        async with UnitOfWork(test_session_factory) as local_uow:
            await SyncService(lambda: UnitOfWork(test_session_factory)).sync(
                local_uow, payload
            )
            raise RuntimeError("fail after synchronization")
    async with UnitOfWork(test_session_factory) as check_uow:
        assert (
            await check_uow.catalog.restaurants.get_by_external_id(external_id)
            is None
        )


@pytest.mark.asyncio
async def test_concurrent_snapshots_same_revision_do_not_both_apply(
    test_session_factory,
) -> None:
    external_id = f"restaurant-{uuid4()}"
    service = SyncService(lambda: UnitOfWork(test_session_factory))

    async def apply(branch_name: str):
        async with UnitOfWork(test_session_factory) as local_uow:
            return await service.sync(
                local_uow,
                make_payload(
                    restaurant_external_id=external_id,
                    revision=1,
                    branch_name=branch_name,
                ),
            )

    results = await asyncio.gather(
        apply("First"),
        apply("Second"),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ConflictError) for result in results) == 1
    assert (
        sum(getattr(result, "status", None) == "updated" for result in results)
        == 1
    )
    async with UnitOfWork(test_session_factory) as check_uow:
        restaurant = await check_uow.catalog.restaurants.get_by_external_id(
            external_id
        )
        branches = (
            await check_uow.catalog.restaurant_branches.get_by_restaurant_id(
                restaurant.id
            )
        )
        assert restaurant.catalog_revision == 1
        assert branches[0].name in {"First", "Second"}
