from app.infrastructure.database.models.sync_snapshot import SyncSnapshot
from app.infrastructure.repositories.base import BaseRepository


class SyncSnapshotRepository(BaseRepository[SyncSnapshot]):
    model = SyncSnapshot
