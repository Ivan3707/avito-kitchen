from app.schemas import ( 
    SyncResponse, 
    SyncPayload, 
    BranchSync, 
    MenuSync, 
    BranchAvailabilitySync, 
    MenuItemSync, 
    MenuItemAvailabilitySync,
    RestaurantSync,
)
from app.infrastructure.unit_of_work import UnitOfWork
from app.core.config import settings


class DemoRestaurantService:
    def __init__(self, session_factory, kitchen_client):
        self.session_factory = session_factory
        self.kitchen_client = kitchen_client

    async def sync(
        self,
        uow: UnitOfWork,
    ) -> SyncResponse:
        return 

    async def build_sync_payload(self) -> SyncPayload:
        async with UnitOfWork(self.session_factory) as uow:
            branches = await uow.restaurant_branches.get_all()
            menu_items = await uow.menu_items.get_all()
            branch_menu_items = await uow.branch_menu_items.get_all()

        branches_data = self._build_branches(branches)
        menu_data = self._build_menu(menu_items)
        availability_data = self._build_availability(
            branches,
            menu_items,
            branch_menu_items,
        )

        return SyncPayload(
            restaurant=RestaurantSync(
                external_id=settings.restaurant_external_id,
                name=settings.restaurant_name,
                description=settings.restaurant_description,
            ),
            branches=branches_data,
            menu=menu_data,
            availability=availability_data,
        )

    def _build_branches(
        self,
        branches,
    ) -> list[BranchSync]:
        branch_data = []
        for branch in branches:
            branch_data.append(
                BranchSync(
                    external_id=branch.external_id,
                    name=branch.name,
                    address=branch.address,
                    is_active=branch.is_active,
                    is_accepting_orders=branch.is_accepting_orders,
                )
            )

        return branch_data

    def _build_menu(
        self,
        menu_items,
    ) -> MenuSync:
        items = []
        for item in menu_items:
            items.append(
                MenuItemSync(
                    external_id=item.external_id,
                    name=item.name,
                    description=item.description,
                    price=item.price,
                    is_active=item.is_active,
                )
            )
        return MenuSync(
            external_id=settings.menu_external_id,
            name=settings.menu_name,
            items=items,
        )

    def _build_availability(
        self,
        branches,
        menu_items,
        branch_menu_items,
    ) -> list[BranchAvailabilitySync]:

        availability_map = {
            (item.branch_id, item.menu_item_id): item.is_available
            for item in branch_menu_items
        }

        availability_data = []

        for branch in branches:
            items = []

            for menu_item in menu_items:
                is_available = availability_map.get(
                    (branch.id, menu_item.id),
                    False,
                )

                items.append(
                    MenuItemAvailabilitySync(
                        menu_item_external_id=menu_item.external_id,
                        is_available=is_available,
                    )
                )

            availability_data.append(
                BranchAvailabilitySync(
                    branch_external_id=branch.external_id,
                    items=items,
                )
            )

        return availability_data
