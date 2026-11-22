from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> T | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == entity_id)
        )

        return result.scalar_one_or_none()

    def add(self, entity: T) -> T:
        self.session.add(entity)
        return entity
