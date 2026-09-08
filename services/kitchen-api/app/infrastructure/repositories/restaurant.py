from sqlalchemy import select

from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.repositories.base import BaseRepository


class RestaurantRepository(BaseRepository[Restaurant]):
    model = Restaurant

    async def get_by_external_id(
        self,
        external_id: str,
    ) -> Restaurant | None:
        result = await self.session.execute(
            select(self.model).where(self.model.external_id == external_id)
        )

        return result.scalar_one_or_none()

    async def get_all(self) -> list[Restaurant]:
        result = await self.session.execute(
            select(self.model).order_by(self.model.name)
        )

        return list(result.scalars().all())
