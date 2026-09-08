from uuid import UUID

from sqlalchemy import select

from app.infrastructure.database.models.order import Order
from app.infrastructure.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    async def get_by_external_id(
        self,
        restaurant_id: UUID,
        external_order_id: str,
    ) -> Order | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.restaurant_id == restaurant_id,
                self.model.external_order_id == external_order_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_restaurant_order_id(
        self,
        restaurant_id: UUID,
        restaurant_order_id: str,
    ) -> Order | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.restaurant_id == restaurant_id,
                self.model.restaurant_order_id == restaurant_order_id,
            )
        )
        return result.scalar_one_or_none()
