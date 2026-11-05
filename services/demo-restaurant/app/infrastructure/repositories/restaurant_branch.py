from sqlalchemy import select

from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.repositories.base import BaseRepository


class RestaurantBranchRepository(BaseRepository[RestaurantBranch]):
    model = RestaurantBranch

    async def get_by_external_id(
        self,
        external_id: str,
    ) -> RestaurantBranch | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[RestaurantBranch]:
        result = await self.session.execute(
            select(self.model).order_by(self.model.id)
        )

        return list(result.scalars().all())