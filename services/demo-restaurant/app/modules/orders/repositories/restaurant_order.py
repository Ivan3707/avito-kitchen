from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.infrastructure.repositories.base import BaseRepository
from app.modules.orders.models.restaurant_order import RestaurantOrder


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

    async def lock_external_id(self, external_id: str) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"restaurant-order:{external_id}"},
        )

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
