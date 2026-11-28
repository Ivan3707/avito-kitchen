from sqlalchemy import select

from app.infrastructure.repositories.base import BaseRepository
from app.modules.catalog.models.menu_item import MenuItem


class MenuItemRepository(BaseRepository[MenuItem]):
    model = MenuItem

    async def get_by_external_id(
        self,
        external_id: str,
    ) -> MenuItem | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.external_id == external_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_all(self) -> list[MenuItem]:
        result = await self.session.execute(
            select(self.model).order_by(self.model.id)
        )

        return list(result.scalars().all())
