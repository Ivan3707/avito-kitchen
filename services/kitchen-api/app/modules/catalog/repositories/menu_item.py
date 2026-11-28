from uuid import UUID

from sqlalchemy import select

from app.infrastructure.repositories.base import BaseRepository
from app.modules.catalog.models.menu_item import MenuItem


class MenuItemRepository(BaseRepository[MenuItem]):
    model = MenuItem

    async def get_by_menu_and_external_id(
        self,
        menu_id: UUID,
        external_id: str,
    ) -> MenuItem | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.menu_id == menu_id,
                self.model.external_id == external_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_by_menu_id(
        self,
        menu_id: UUID,
    ) -> list[MenuItem]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.menu_id == menu_id)
            .order_by(self.model.name)
        )

        return list(result.scalars().all())
