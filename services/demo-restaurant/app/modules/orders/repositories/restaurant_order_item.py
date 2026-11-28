from uuid import UUID

from sqlalchemy import select

from app.infrastructure.repositories.base import BaseRepository
from app.modules.orders.models.restaurant_order_item import (
    RestaurantOrderItem,
)


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
