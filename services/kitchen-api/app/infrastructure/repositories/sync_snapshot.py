from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, text

from app.infrastructure.database.models.sync_snapshot import SyncSnapshot
from app.infrastructure.repositories.base import BaseRepository


class SyncSnapshotRepository(BaseRepository[SyncSnapshot]):
    model = SyncSnapshot

    async def get_by_id(self, snapshot_id: UUID) -> SyncSnapshot | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.snapshot_id == snapshot_id,
            )
        )
        return result.scalar_one_or_none()

    async def lock_id(self, snapshot_id: UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 1))"),
            {"key": str(snapshot_id)},
        )

    async def delete_processed_before(
        self,
        restaurant_id: UUID,
        cutoff: datetime,
    ) -> None:
        await self.session.execute(
            delete(self.model).where(
                self.model.restaurant_id == restaurant_id,
                self.model.processed_at < cutoff,
            )
        )
