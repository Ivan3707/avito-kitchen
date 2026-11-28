from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.repositories.order import OrderRepository


class OrderRepositories:
    def __init__(self, session: AsyncSession):
        self.orders = OrderRepository(session)
