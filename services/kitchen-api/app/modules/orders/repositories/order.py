from uuid import UUID

from sqlalchemy import select, text

from app.infrastructure.repositories.base import BaseRepository
from app.modules.orders.models.order import Order


class OrderRepository(BaseRepository[Order]):
    model = Order

    async def lock_external_id(
        self,
        restaurant_id: UUID,
        external_order_id: str,
    ) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"kitchen-order:{restaurant_id}:{external_order_id}"},
        )

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

    async def get_by_external_id_for_update(
        self,
        restaurant_id: UUID,
        external_order_id: str,
    ) -> Order | None:
        result = await self.session.execute(
            select(self.model)
            .where(
                self.model.restaurant_id == restaurant_id,
                self.model.external_order_id == external_order_id,
            )
            .with_for_update()
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
