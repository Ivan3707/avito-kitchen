from uuid import UUID

from sqlalchemy import select

from app.infrastructure.repositories.base import BaseRepository
from app.modules.catalog.models.restaurant_branch import (
    RestaurantBranch,
)


class RestaurantBranchRepository(BaseRepository[RestaurantBranch]):
    model = RestaurantBranch

    async def get_by_restaurant_and_external_id(
        self,
        restaurant_id: UUID,
        external_id: str,
    ) -> RestaurantBranch | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.restaurant_id == restaurant_id,
                self.model.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_restaurant_and_external_id_for_update(
        self,
        restaurant_id: UUID,
        external_id: str,
    ) -> RestaurantBranch | None:
        result = await self.session.execute(
            select(self.model)
            .where(
                self.model.restaurant_id == restaurant_id,
                self.model.external_id == external_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_external_id_any_restaurant(
        self,
        external_id: str,
    ) -> RestaurantBranch | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_restaurant_id(
        self,
        restaurant_id: UUID,
    ) -> list[RestaurantBranch]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.restaurant_id == restaurant_id)
            .order_by(self.model.name)
        )

        return list(result.scalars().all())
