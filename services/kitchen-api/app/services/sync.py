from app.infrastructure.database.models.branch_menu_item import BranchMenuItem
from app.infrastructure.database.models.menu import Menu
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.sync import (
    IgnoredSyncResponse,
    SyncPayload,
    SyncResponse,
    UpdatedSyncResponse,
)


class SyncService:
    async def sync(
        self,
        uow: UnitOfWork,
        payload: SyncPayload,
    ) -> SyncResponse:
        # Restaurant
        restaurant = await uow.restaurants.get_by_external_id(
            payload.restaurant.external_id
        )

        if restaurant is not None:
            if payload.version <= restaurant.sync_version:
                return IgnoredSyncResponse(
                    version=restaurant.sync_version,
                )

            restaurant.name = payload.restaurant.name
            restaurant.description = payload.restaurant.description
            restaurant.sync_version = payload.version

        else:
            restaurant = uow.restaurants.add(
                Restaurant(
                    external_id=payload.restaurant.external_id,
                    name=payload.restaurant.name,
                    description=payload.restaurant.description,
                    sync_version=payload.version,
                )
            )

        await uow.session.flush()

        # Branches
        existing_branches = await uow.restaurant_branches.get_by_restaurant_id(
            restaurant.id
        )

        existing_branches_by_external_id = {
            branch.external_id: branch for branch in existing_branches
        }

        payload_branch_ids = {
            branch_data.external_id for branch_data in payload.branches
        }

        branches_by_external_id: dict[str, RestaurantBranch] = {}

        for branch_data in payload.branches:
            branch = existing_branches_by_external_id.get(
                branch_data.external_id
            )

            if branch is None:
                branch = uow.restaurant_branches.add(
                    RestaurantBranch(
                        restaurant_id=restaurant.id,
                        external_id=branch_data.external_id,
                        name=branch_data.name,
                        address=branch_data.address,
                        is_active=branch_data.is_active,
                        is_accepting_orders=branch_data.is_accepting_orders,
                    )
                )
            else:
                branch.name = branch_data.name
                branch.address = branch_data.address
                branch.is_active = branch_data.is_active
                branch.is_accepting_orders = branch_data.is_accepting_orders

            branches_by_external_id[branch.external_id] = branch

        # Full sync:
        # branches missing from the new payload are no longer active.
        for branch in existing_branches:
            if branch.external_id not in payload_branch_ids:
                branch.is_active = False
                branch.is_accepting_orders = False

        await uow.session.flush()

        # Menu
        menu = await uow.menus.get_by_restaurant_id(restaurant.id)

        if menu is None:
            menu = uow.menus.add(
                Menu(
                    restaurant_id=restaurant.id,
                    external_id=payload.menu.external_id,
                    name=payload.menu.name,
                )
            )
        else:
            menu.external_id = payload.menu.external_id
            menu.name = payload.menu.name

        await uow.session.flush()

        # Menu items
        existing_menu_items = await uow.menu_items.get_by_menu_id(menu.id)

        existing_menu_items_by_external_id = {
            item.external_id: item for item in existing_menu_items
        }

        payload_menu_item_ids = {
            item_data.external_id for item_data in payload.menu.items
        }

        menu_items_by_external_id: dict[str, MenuItem] = {}

        for item_data in payload.menu.items:
            item = existing_menu_items_by_external_id.get(
                item_data.external_id
            )

            if item is None:
                item = uow.menu_items.add(
                    MenuItem(
                        menu_id=menu.id,
                        external_id=item_data.external_id,
                        name=item_data.name,
                        description=item_data.description,
                        price=item_data.price,
                        is_active=item_data.is_active,
                    )
                )
            else:
                item.name = item_data.name
                item.description = item_data.description
                item.price = item_data.price
                item.is_active = item_data.is_active

            menu_items_by_external_id[item.external_id] = item

        # Full sync:
        # menu items missing from the new payload are no longer active.
        for item in existing_menu_items:
            if item.external_id not in payload_menu_item_ids:
                item.is_active = False

        await uow.session.flush()

        # Branch availability
        for branch_availability in payload.availability:
            branch = branches_by_external_id[
                branch_availability.branch_external_id
            ]

            existing_branch_items = (
                await uow.branch_menu_items.get_all_by_branch(branch.id)
            )

            existing_branch_items_by_menu_item_id = {
                branch_item.menu_item_id: branch_item
                for branch_item in existing_branch_items
            }

            payload_availability_item_ids = {
                availability_data.menu_item_external_id
                for availability_data in branch_availability.items
            }

            for availability_data in branch_availability.items:
                menu_item = menu_items_by_external_id[
                    availability_data.menu_item_external_id
                ]

                branch_menu_item = existing_branch_items_by_menu_item_id.get(
                    menu_item.id
                )

                if branch_menu_item is None:
                    uow.branch_menu_items.add(
                        BranchMenuItem(
                            branch_id=branch.id,
                            menu_item_id=menu_item.id,
                            is_available=availability_data.is_available,
                        )
                    )
                else:
                    branch_menu_item.is_available = (
                        availability_data.is_available
                    )

            # Existing branch-menu relations for menu items that are no
            # longer present in the current menu are no longer available.
            for branch_menu_item in existing_branch_items:
                menu_item = branch_menu_item.menu_item

                if menu_item.external_id not in payload_availability_item_ids:
                    branch_menu_item.is_available = False

            # An inactive branch cannot expose available products.
            if not branch.is_active:
                for branch_menu_item in existing_branch_items:
                    branch_menu_item.is_available = False

        return UpdatedSyncResponse(
            version=payload.version,
        )
