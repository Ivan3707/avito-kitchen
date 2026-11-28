from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.errors import ConflictError
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu import Menu
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant import Restaurant
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)
from app.modules.catalog.models.sync_snapshot import SyncSnapshot
from app.modules.catalog.sync.checksum import catalog_checksum
from app.modules.catalog.sync.schemas import (
    IgnoredSyncResponse,
    SyncPayload,
    SyncResponse,
    UpdatedSyncResponse,
)

SNAPSHOT_RETENTION = timedelta(days=30)


class SyncService:
    def __init__(self, uow_factory=None):
        self.uow_factory = uow_factory

    async def apply(self, payload: SyncPayload) -> SyncResponse:
        async with self.uow_factory() as uow:
            return await self.sync(uow, payload)

    async def sync(
        self, uow: UnitOfWork, payload: SyncPayload
    ) -> SyncResponse:
        external_id = payload.restaurant.external_id
        checksum = catalog_checksum(payload)

        await uow.catalog.restaurants.lock_external_id(external_id)
        await uow.catalog.sync_snapshots.lock_id(payload.snapshot_id)

        known_snapshot = await uow.catalog.sync_snapshots.get_by_id(
            payload.snapshot_id
        )
        if known_snapshot is not None:
            response = await self._handle_known_snapshot(
                uow, payload, checksum, known_snapshot
            )
            await self._delete_expired_history(
                uow, known_snapshot.restaurant_id
            )
            return response

        snapshot_owner = await uow.catalog.restaurants.get_by_last_snapshot_id(
            payload.snapshot_id
        )
        if snapshot_owner is not None:
            matches = (
                snapshot_owner.external_id == external_id
                and snapshot_owner.catalog_revision == payload.catalog_revision
                and snapshot_owner.catalog_checksum == checksum
            )
            if not matches:
                raise ConflictError(
                    "snapshot_id is retained as another current or legacy "
                    "snapshot"
                )
            await self._delete_expired_history(uow, snapshot_owner.id)
            return IgnoredSyncResponse(
                snapshot_id=payload.snapshot_id,
                reason="DUPLICATE_SNAPSHOT",
            )

        restaurant = (
            await uow.catalog.restaurants.get_by_external_id_for_update(
                external_id
            )
        )
        if restaurant is not None and restaurant.catalog_revision is not None:
            if payload.catalog_revision < restaurant.catalog_revision:
                self._record_snapshot(uow, restaurant, payload, checksum)
                await self._delete_expired_history(uow, restaurant.id)
                return IgnoredSyncResponse(
                    snapshot_id=payload.snapshot_id,
                    reason="STALE_SNAPSHOT",
                )

            if payload.catalog_revision == restaurant.catalog_revision:
                if checksum != restaurant.catalog_checksum:
                    raise ConflictError(
                        "catalog revision already exists with different "
                        "business content"
                    )
                self._record_snapshot(uow, restaurant, payload, checksum)
                await self._delete_expired_history(uow, restaurant.id)
                return IgnoredSyncResponse(
                    snapshot_id=payload.snapshot_id,
                    reason="DUPLICATE_STATE",
                )

        restaurant = await self._apply_snapshot(uow, restaurant, payload)
        restaurant.catalog_revision = payload.catalog_revision
        restaurant.catalog_checksum = checksum
        restaurant.last_snapshot_id = payload.snapshot_id
        restaurant.last_snapshot_generated_at = payload.generated_at
        self._record_snapshot(uow, restaurant, payload, checksum)
        await self._delete_expired_history(uow, restaurant.id)
        return UpdatedSyncResponse(snapshot_id=payload.snapshot_id)

    async def _handle_known_snapshot(
        self,
        uow: UnitOfWork,
        payload: SyncPayload,
        checksum: str,
        known_snapshot: SyncSnapshot,
    ) -> IgnoredSyncResponse:
        known_restaurant = await uow.catalog.restaurants.get_by_id(
            known_snapshot.restaurant_id
        )
        matches = (
            known_restaurant is not None
            and known_restaurant.external_id == payload.restaurant.external_id
            and known_snapshot.catalog_revision == payload.catalog_revision
            and known_snapshot.catalog_checksum == checksum
        )
        if not matches:
            raise ConflictError(
                "snapshot_id already exists with different identity, "
                "revision, or business content"
            )
        return IgnoredSyncResponse(
            snapshot_id=payload.snapshot_id,
            reason="DUPLICATE_SNAPSHOT",
        )

    async def _apply_snapshot(
        self,
        uow: UnitOfWork,
        restaurant: Restaurant | None,
        payload: SyncPayload,
    ) -> Restaurant:
        if restaurant is None:
            restaurant = uow.catalog.restaurants.add(
                Restaurant(
                    external_id=payload.restaurant.external_id,
                    name=payload.restaurant.name,
                    description=payload.restaurant.description,
                )
            )
            await uow.flush()
        else:
            restaurant.name = payload.restaurant.name
            restaurant.description = payload.restaurant.description

        existing_branches = (
            await uow.catalog.restaurant_branches.get_by_restaurant_id(
                restaurant.id
            )
        )
        branches_by_external_id = {
            branch.external_id: branch for branch in existing_branches
        }
        incoming_branch_ids = {
            branch.external_id for branch in payload.branches
        }
        for branch_data in payload.branches:
            branch = branches_by_external_id.get(branch_data.external_id)
            if branch is None:
                branch = uow.catalog.restaurant_branches.add(
                    RestaurantBranch(
                        restaurant_id=restaurant.id,
                        external_id=branch_data.external_id,
                        name=branch_data.name,
                        address=branch_data.address,
                        is_active=branch_data.is_active,
                        is_accepting_orders=branch_data.is_accepting_orders,
                    )
                )
                branches_by_external_id[branch_data.external_id] = branch
            else:
                branch.name = branch_data.name
                branch.address = branch_data.address
                branch.is_active = branch_data.is_active
                branch.is_accepting_orders = branch_data.is_accepting_orders

        for branch in existing_branches:
            if branch.external_id not in incoming_branch_ids:
                branch.is_active = False
                branch.is_accepting_orders = False
        await uow.flush()

        menu = await uow.catalog.menus.get_by_restaurant_id(restaurant.id)
        if menu is None:
            menu = uow.catalog.menus.add(
                Menu(
                    restaurant_id=restaurant.id,
                    external_id=payload.menu.external_id,
                    name=payload.menu.name,
                )
            )
            await uow.flush()
        else:
            menu.external_id = payload.menu.external_id
            menu.name = payload.menu.name

        existing_items = await uow.catalog.menu_items.get_by_menu_id(menu.id)
        items_by_external_id = {
            item.external_id: item for item in existing_items
        }
        incoming_item_ids = {item.external_id for item in payload.menu.items}
        for item_data in payload.menu.items:
            item = items_by_external_id.get(item_data.external_id)
            if item is None:
                item = uow.catalog.menu_items.add(
                    MenuItem(
                        menu_id=menu.id,
                        external_id=item_data.external_id,
                        name=item_data.name,
                        description=item_data.description,
                        is_active=item_data.is_active,
                    )
                )
                items_by_external_id[item_data.external_id] = item
            else:
                item.name = item_data.name
                item.description = item_data.description
                item.is_active = item_data.is_active

        for item in existing_items:
            if item.external_id not in incoming_item_ids:
                item.is_active = False
        await uow.flush()

        availability_by_branch = {
            entry.branch_external_id: entry for entry in payload.availability
        }
        for branch in branches_by_external_id.values():
            existing_relations = (
                await uow.catalog.branch_menu_items.get_all_by_branch(
                    branch.id
                )
            )
            relations_by_item_id = {
                relation.menu_item_id: relation
                for relation in existing_relations
            }
            for relation in existing_relations:
                relation.is_available = False
                relation.price = None

            availability = availability_by_branch.get(branch.external_id)
            if availability is None:
                continue

            for availability_data in availability.items:
                item = items_by_external_id[
                    availability_data.menu_item_external_id
                ]
                relation = relations_by_item_id.get(item.id)
                is_available = (
                    availability_data.is_available
                    and branch.is_active
                    and item.is_active
                )
                if relation is None:
                    if availability_data.price is None and not is_available:
                        continue
                    uow.catalog.branch_menu_items.add(
                        BranchMenuItem(
                            branch_id=branch.id,
                            menu_item_id=item.id,
                            is_available=is_available,
                            price=availability_data.price,
                        )
                    )
                else:
                    relation.is_available = is_available
                    relation.price = availability_data.price

        return restaurant

    @staticmethod
    def _record_snapshot(
        uow: UnitOfWork,
        restaurant: Restaurant,
        payload: SyncPayload,
        checksum: str,
    ) -> None:
        uow.catalog.sync_snapshots.add(
            SyncSnapshot(
                snapshot_id=payload.snapshot_id,
                restaurant_id=restaurant.id,
                generated_at=payload.generated_at,
                catalog_revision=payload.catalog_revision,
                catalog_checksum=checksum,
            )
        )

    @staticmethod
    async def _delete_expired_history(
        uow: UnitOfWork,
        restaurant_id: UUID,
    ) -> None:
        cutoff = datetime.now(UTC) - SNAPSHOT_RETENTION
        await uow.catalog.sync_snapshots.delete_processed_before(
            restaurant_id,
            cutoff,
        )
