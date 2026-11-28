from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.repositories.restaurant_order import (
    RestaurantOrderRepository,
)


class OrderRepositories:
    def __init__(self, session: AsyncSession):
        self.restaurant_orders = RestaurantOrderRepository(session)
