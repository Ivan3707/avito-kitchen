from uuid import UUID

from sqlalchemy import select

from app.infrastructure.database.models.restaurant_order_item import (
    RestaurantOrderItem,
)
from app.infrastructure.repositories.base import BaseRepository


class RestaurantOrderItemRepository(BaseRepository[RestaurantOrderItem]):
    model = RestaurantOrderItem

    async def get_all_by_order(
        self,
        order_id: UUID,
    ) -> list[RestaurantOrderItem]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.order_id == order_id)
            .order_by(self.model.id)
        )

        return list(result.scalars().all())