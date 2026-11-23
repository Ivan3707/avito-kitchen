from app.infrastructure.database.models.branch_menu_item import BranchMenuItem
from app.infrastructure.database.models.menu import Menu
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.database.models.sync_snapshot import SyncSnapshot
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.sync import (
    IgnoredSyncResponse,
    SyncPayload,
    SyncResponse,
    UpdatedSyncResponse,
)


class SyncService:
    async def sync(
        self, uow: UnitOfWork, payload: SyncPayload
    ) -> SyncResponse:
        external_id = payload.restaurant.external_id
        await uow.restaurants.lock_external_id(external_id)

        if await uow.sync_snapshots.get_by_id(payload.snapshot_id) is not None:
            return IgnoredSyncResponse(
                snapshot_id=payload.snapshot_id,
                reason="DUPLICATE_SNAPSHOT",
            )

        restaurant = await uow.restaurants.get_by_external_id_for_update(
            external_id
        )
        if restaurant is not None and self._is_stale_by_time(
            restaurant, payload
        ):
            return IgnoredSyncResponse(
                snapshot_id=payload.snapshot_id,
                reason="STALE_SNAPSHOT",
            )

        if restaurant is None:
            restaurant = uow.restaurants.add(
                Restaurant(
                    external_id=external_id,
                    name=payload.restaurant.name,
                    description=payload.restaurant.description,
                )
            )
            await uow.flush()
        else:
            existing_for_version_check = (
                await uow.restaurant_branches.get_by_restaurant_id(
                    restaurant.id
                )
            )
            incoming_versions = {
                branch.external_id: branch.branch_version
                for branch in payload.branches
            }
            if any(
                branch.external_id in incoming_versions
                and incoming_versions[branch.external_id]
                < branch.branch_version
                for branch in existing_for_version_check
            ):
                return IgnoredSyncResponse(
                    snapshot_id=payload.snapshot_id,
                    reason="STALE_SNAPSHOT",
                )
            restaurant.name = payload.restaurant.name
            restaurant.description = payload.restaurant.description

        existing_branches = await uow.restaurant_branches.get_by_restaurant_id(
            restaurant.id
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
                branch = uow.restaurant_branches.add(
                    RestaurantBranch(
                        restaurant_id=restaurant.id,
                        external_id=branch_data.external_id,
                        name=branch_data.name,
                        address=branch_data.address,
                        is_active=branch_data.is_active,
                        is_accepting_orders=branch_data.is_accepting_orders,
                        branch_version=branch_data.branch_version,
                    )
                )
                branches_by_external_id[branch_data.external_id] = branch
            else:
                branch.name = branch_data.name
                branch.address = branch_data.address
                branch.is_active = branch_data.is_active
                branch.is_accepting_orders = branch_data.is_accepting_orders
                branch.branch_version = branch_data.branch_version

        for branch in existing_branches:
            if branch.external_id not in incoming_branch_ids:
                branch.is_active = False
                branch.is_accepting_orders = False

        await uow.flush()

        menu = await uow.menus.get_by_restaurant_id(restaurant.id)
        if menu is None:
            menu = uow.menus.add(
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

        existing_items = await uow.menu_items.get_by_menu_id(menu.id)
        items_by_external_id = {
            item.external_id: item for item in existing_items
        }
        incoming_item_ids = {item.external_id for item in payload.menu.items}
        for item_data in payload.menu.items:
            item = items_by_external_id.get(item_data.external_id)
            if item is None:
                item = uow.menu_items.add(
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
            existing_relations = await uow.branch_menu_items.get_all_by_branch(
                branch.id
            )
            relations_by_item_id = {
                relation.menu_item_id: relation
                for relation in existing_relations
            }
            for relation in existing_relations:
                relation.is_available = False

            availability = availability_by_branch.get(branch.external_id)
            if availability is None:
                continue

            for availability_data in availability.items:
                item = items_by_external_id[
                    availability_data.menu_item_external_id
                ]
                relation = relations_by_item_id.get(item.id)
                value = (
                    availability_data.is_available
                    and branch.is_active
                    and item.is_active
                )
                if relation is None:
                    if availability_data.price is None and not value:
                        continue
                    uow.branch_menu_items.add(
                        BranchMenuItem(
                            branch_id=branch.id,
                            menu_item_id=item.id,
                            is_available=value,
                            price=availability_data.price,
                        )
                    )
                else:
                    relation.is_available = value
                    relation.price = availability_data.price

        restaurant.last_snapshot_id = payload.snapshot_id
        restaurant.last_snapshot_generated_at = payload.generated_at
        uow.sync_snapshots.add(
            SyncSnapshot(
                snapshot_id=payload.snapshot_id,
                restaurant_id=restaurant.id,
                generated_at=payload.generated_at,
            )
        )
        return UpdatedSyncResponse(snapshot_id=payload.snapshot_id)

    @staticmethod
    def _is_stale_by_time(
        restaurant: Restaurant,
        payload: SyncPayload,
    ) -> bool:
        current = restaurant.last_snapshot_generated_at
        return current is not None and payload.generated_at <= current
