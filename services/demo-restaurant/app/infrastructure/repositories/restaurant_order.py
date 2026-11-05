from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models.restaurant_order import RestaurantOrder
from app.infrastructure.repositories.base import BaseRepository


class RestaurantOrderRepository(BaseRepository[RestaurantOrder]):
    model = RestaurantOrder

    async def get_by_external_id(
        self,
        external_id: str,
    ) -> RestaurantOrder | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.external_id == external_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_with_items_by_external_id(
        self,
        external_id: str,
    ) -> RestaurantOrder | None:
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(self.model.items))
            .where(self.model.external_id == external_id)
        )

        return result.scalar_one_or_none()