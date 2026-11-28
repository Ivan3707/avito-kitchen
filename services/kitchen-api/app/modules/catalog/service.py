from uuid import UUID

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.schemas import (
    BranchMenuResponse,
    BranchResponse,
    MenuItemResponse,
    RestaurantResponse,
)


class CatalogService:
    def __init__(self, uow_factory=None):
        self.uow_factory = uow_factory

    async def list_restaurants(self) -> list[RestaurantResponse]:
        async with self.uow_factory() as uow:
            return await self.get_restaurants(uow)

    async def list_branches(self, restaurant_id: UUID) -> list[BranchResponse]:
        async with self.uow_factory() as uow:
            return await self.get_branches(uow, restaurant_id)

    async def get_menu(self, branch_id: UUID) -> BranchMenuResponse:
        async with self.uow_factory() as uow:
            return await self.get_branch_menu(uow, branch_id)

    async def get_restaurants(
        self,
        uow: UnitOfWork,
    ) -> list[RestaurantResponse]:
        restaurants = await uow.catalog.restaurants.get_all()

        return [
            RestaurantResponse(
                id=restaurant.id,
                name=restaurant.name,
                description=restaurant.description,
            )
            for restaurant in restaurants
        ]

    async def get_branches(
        self,
        uow: UnitOfWork,
        restaurant_id: UUID,
    ) -> list[BranchResponse]:
        branches = await uow.catalog.restaurant_branches.get_by_restaurant_id(
            restaurant_id
        )

        return [
            BranchResponse(
                id=branch.id,
                name=branch.name,
                address=branch.address,
                is_active=branch.is_active,
                is_accepting_orders=branch.is_accepting_orders,
            )
            for branch in branches
        ]

    async def get_branch_menu(
        self,
        uow: UnitOfWork,
        branch_id: UUID,
    ) -> BranchMenuResponse:
        branch_menu_items = (
            await uow.catalog.branch_menu_items.get_all_by_branch(branch_id)
        )

        items = [
            MenuItemResponse(
                id=item.menu_item.id,
                external_id=item.menu_item.external_id,
                name=item.menu_item.name,
                description=item.menu_item.description,
                price=item.price,
                is_available=(
                    item.is_available
                    and item.price is not None
                    and item.menu_item.is_active
                ),
            )
            for item in branch_menu_items
        ]

        return BranchMenuResponse(
            branch_id=branch_id,
            items=items,
        )
