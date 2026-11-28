from uuid import UUID

from sqlalchemy import select, text

from app.infrastructure.repositories.base import BaseRepository
from app.modules.catalog.models.restaurant import Restaurant


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

    async def get_by_last_snapshot_id(
        self,
        snapshot_id: UUID,
    ) -> Restaurant | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.last_snapshot_id == snapshot_id
            )
        )
        return result.scalar_one_or_none()

    async def lock_external_id(self, external_id: str) -> None:
        """Serialize creation and snapshot application for one restaurant."""
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": external_id},
        )

    async def get_by_external_id_for_update(
        self,
        external_id: str,
    ) -> Restaurant | None:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.external_id == external_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Restaurant]:
        result = await self.session.execute(
            select(self.model).order_by(self.model.name)
        )

        return list(result.scalars().all())
