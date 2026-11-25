from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update

from app.infrastructure.database.models.user_action_token import (
    UserActionToken,
)
from app.infrastructure.repositories.base import BaseRepository


class UserActionTokenRepository(BaseRepository[UserActionToken]):
    model = UserActionToken

    async def get_by_hash(self, token_hash: str) -> UserActionToken | None:
        result = await self.session.execute(
            select(self.model).where(self.model.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_hash_for_update(
        self, token_hash: str
    ) -> UserActionToken | None:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def latest_created_at(
        self, user_id: UUID, purpose: str
    ) -> datetime | None:
        return await self.session.scalar(
            select(func.max(self.model.created_at)).where(
                self.model.user_id == user_id,
                self.model.purpose == purpose,
            )
        )

    async def count_created_since(
        self,
        user_id: UUID,
        purpose: str,
        since: datetime,
    ) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.purpose == purpose,
                self.model.created_at >= since,
            )
        )
        return count or 0

    async def revoke_active(
        self,
        user_id: UUID,
        purpose: str,
        revoked_at: datetime,
        exclude_id: UUID | None = None,
    ) -> None:
        statement = update(self.model).where(
            self.model.user_id == user_id,
            self.model.purpose == purpose,
            self.model.used_at.is_(None),
            self.model.revoked_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(self.model.id != exclude_id)
        await self.session.execute(statement.values(revoked_at=revoked_at))
