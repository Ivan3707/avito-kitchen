from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models.branch_menu_item import BranchMenuItem
from app.infrastructure.repositories.base import BaseRepository


class BranchMenuItemRepository(BaseRepository[BranchMenuItem]):
    model = BranchMenuItem

    async def get_by_branch_and_menu_item(
        self,
        branch_id: UUID,
        menu_item_id: UUID,
    ) -> BranchMenuItem | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.branch_id == branch_id,
                self.model.menu_item_id == menu_item_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_menu_item(
        self,
        branch_id: UUID,
        menu_item_id: UUID,
    ) -> BranchMenuItem | None:
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(self.model.menu_item))
            .where(
                self.model.branch_id == branch_id,
                self.model.menu_item_id == menu_item_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_branch(
        self,
        branch_id: UUID,
    ) -> list[BranchMenuItem]:
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(self.model.menu_item))
            .where(self.model.branch_id == branch_id)
            .order_by(self.model.id)
        )

        return list(result.scalars().all())
