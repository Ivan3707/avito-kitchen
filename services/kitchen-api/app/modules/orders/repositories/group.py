from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.repositories.order import OrderRepository
from app.modules.orders.repositories.order_item import OrderItemRepository


class OrderRepositories:
    def __init__(self, session: AsyncSession):
        self.orders = OrderRepository(session)
        self.order_items = OrderItemRepository(session)
