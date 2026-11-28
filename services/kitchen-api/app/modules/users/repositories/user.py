from uuid import UUID

from sqlalchemy import select, text

from app.infrastructure.repositories.base import BaseRepository
from app.modules.users.models.user import User


class UserRepository(BaseRepository[User]):
    model = User

    async def lock_email(self, email: str) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"user:{email}"},
        )

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_email_for_update(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.email == email)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()
