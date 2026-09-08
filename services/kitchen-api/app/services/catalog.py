from uuid import UUID

from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.catalog import (
    BranchMenuResponse,
    BranchResponse,
    MenuItemResponse,
    RestaurantResponse,
)


class CatalogService:
    async def get_restaurants(
        self,
        uow: UnitOfWork,
    ) -> list[RestaurantResponse]:
        restaurants = await uow.restaurants.get_all()

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
        branches = await uow.restaurant_branches.get_by_restaurant_id(
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
        branch_menu_items = await uow.branch_menu_items.get_all_by_branch(
            branch_id
        )

        items = [
            MenuItemResponse(
                id=item.menu_item.id,
                external_id=item.menu_item.external_id,
                name=item.menu_item.name,
                description=item.menu_item.description,
                price=item.menu_item.price,
                is_available=item.is_available and item.menu_item.is_active,
            )
            for item in branch_menu_items
        ]

        return BranchMenuResponse(
            branch_id=branch_id,
            items=items,
        )
