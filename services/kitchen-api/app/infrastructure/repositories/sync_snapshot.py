from uuid import UUID

from sqlalchemy import select

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
