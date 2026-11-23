from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.catalog_state import CatalogState


class CatalogStateRepository:
    _STATE_ID = 1

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current(self) -> CatalogState:
        result = await self.session.execute(
            select(CatalogState).where(CatalogState.id == self._STATE_ID)
        )
        return self._require_state(result.scalar_one_or_none())

    async def get_for_update(self) -> CatalogState:
        result = await self.session.execute(
            select(CatalogState)
            .where(CatalogState.id == self._STATE_ID)
            .with_for_update()
        )
        return self._require_state(result.scalar_one_or_none())

    async def increment(self) -> int:
        state = await self.get_for_update()
        state.catalog_revision += 1
        return state.catalog_revision

    @staticmethod
    def _require_state(state: CatalogState | None) -> CatalogState:
        if state is None:
            raise RuntimeError("catalog state row is missing")
        return state
