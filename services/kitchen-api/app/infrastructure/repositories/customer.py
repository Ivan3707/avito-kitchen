from sqlalchemy import select, text

from app.infrastructure.database.models.customer import Customer
from app.infrastructure.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def lock_email(self, email: str) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"customer:{email}"},
        )

    async def get_by_email(
        self,
        email: str,
    ) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.email == email)
        )

        return result.scalar_one_or_none()
