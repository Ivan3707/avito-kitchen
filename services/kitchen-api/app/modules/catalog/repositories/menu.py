from uuid import UUID

from sqlalchemy import select

from app.infrastructure.repositories.base import BaseRepository
from app.modules.catalog.models.menu import Menu


class MenuRepository(BaseRepository[Menu]):
    model = Menu

    async def get_by_restaurant_id(
        self,
        restaurant_id: UUID,
    ) -> Menu | None:
        result = await self.session.execute(
            select(Menu).where(Menu.restaurant_id == restaurant_id)
        )

        return result.scalar_one_or_none()
