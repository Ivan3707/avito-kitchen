from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import settings
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.sync.schemas import (
    BranchAvailabilitySync,
    BranchSync,
    MenuItemAvailabilitySync,
    MenuItemSync,
    MenuSync,
    RestaurantSync,
    SyncPayload,
    SyncResponse,
)


class CatalogSyncService:
    def __init__(self, session_factory, kitchen_client):
        self.session_factory = session_factory
        self.kitchen_client = kitchen_client

    async def sync(self) -> SyncResponse:
        payload = await self.build_sync_payload()
        response = await self.kitchen_client.sync_catalog(
            payload.model_dump(mode="json")
        )
        return SyncResponse.model_validate(response)

    async def build_sync_payload(self) -> SyncPayload:
        async with UnitOfWork(
            self.session_factory,
            isolation_level="REPEATABLE READ",
        ) as uow:
            branches = await uow.catalog.restaurant_branches.get_all()
            menu_items = await uow.catalog.menu_items.get_all()
            branch_menu_items = await uow.catalog.branch_menu_items.get_all()
            catalog_state = await uow.catalog.catalog_state.get_current()
            return SyncPayload(
                snapshot_id=uuid4(),
                schema_version=3,
                catalog_revision=catalog_state.catalog_revision,
                generated_at=datetime.now(UTC),
                restaurant=RestaurantSync(
                    external_id=settings.restaurant_external_id,
                    name=catalog_state.restaurant_name,
                    description=catalog_state.restaurant_description,
                ),
                branches=self._build_branches(branches),
                menu=self._build_menu(menu_items, catalog_state.menu_name),
                availability=self._build_availability(
                    branches, menu_items, branch_menu_items
                ),
            )

    @staticmethod
    def _build_branches(branches) -> list[BranchSync]:
        return [
            BranchSync(
                external_id=branch.external_id,
                name=branch.name,
                address=branch.address,
                is_active=branch.is_active,
                is_accepting_orders=branch.is_accepting_orders,
            )
            for branch in branches
        ]

    @staticmethod
    def _build_menu(menu_items, menu_name: str) -> MenuSync:
        return MenuSync(
            external_id=settings.menu_external_id,
            name=menu_name,
            items=[
                MenuItemSync(
                    external_id=item.external_id,
                    name=item.name,
                    description=item.description,
                    is_active=item.is_active,
                )
                for item in menu_items
            ],
        )

    @staticmethod
    def _build_availability(
        branches, menu_items, branch_menu_items
    ) -> list[BranchAvailabilitySync]:
        availability_map = {
            (item.branch_id, item.menu_item_id): item
            for item in branch_menu_items
        }
        return [
            BranchAvailabilitySync(
                branch_external_id=branch.external_id,
                items=[
                    MenuItemAvailabilitySync(
                        menu_item_external_id=menu_item.external_id,
                        price=(
                            relation.price if relation is not None else None
                        ),
                        is_available=(
                            relation is not None
                            and relation.is_available
                            and relation.price is not None
                            and branch.is_active
                            and menu_item.is_active
                        ),
                    )
                    for menu_item in menu_items
                    for relation in [
                        availability_map.get((branch.id, menu_item.id))
                    ]
                ],
            )
            for branch in branches
        ]
