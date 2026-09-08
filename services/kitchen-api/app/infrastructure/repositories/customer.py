from sqlalchemy import select

from app.infrastructure.database.models.customer import Customer
from app.infrastructure.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def get_by_email(
        self,
        email: str,
    ) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.email == email)
        )

        return result.scalar_one_or_none()
