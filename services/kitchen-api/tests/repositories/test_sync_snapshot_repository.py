from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.infrastructure.database.models.restaurant import Restaurant
from app.infrastructure.database.models.sync_snapshot import SyncSnapshot
from app.infrastructure.repositories.restaurant import RestaurantRepository
from app.infrastructure.repositories.sync_snapshot import (
    SyncSnapshotRepository,
)


@pytest.mark.asyncio
async def test_get_by_id_uses_snapshot_primary_key(test_session_factory):
    snapshot_id = uuid4()

    async with test_session_factory() as session:
        restaurant = RestaurantRepository(session).add(
            Restaurant(
                external_id=f"restaurant-{uuid4()}",
                name="Test Restaurant",
            )
        )
        await session.flush()
        SyncSnapshotRepository(session).add(
            SyncSnapshot(
                snapshot_id=snapshot_id,
                restaurant_id=restaurant.id,
                generated_at=datetime.now(UTC),
            )
        )
        await session.commit()

    async with test_session_factory() as session:
        saved_snapshot = await SyncSnapshotRepository(session).get_by_id(
            snapshot_id
        )

    assert saved_snapshot is not None
    assert saved_snapshot.snapshot_id == snapshot_id
