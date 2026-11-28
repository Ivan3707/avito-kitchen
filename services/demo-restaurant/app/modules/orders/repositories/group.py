from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.repositories.restaurant_order import (
    RestaurantOrderRepository,
)
from app.modules.orders.repositories.restaurant_order_item import (
    RestaurantOrderItemRepository,
)


class OrderRepositories:
    def __init__(self, session: AsyncSession):
        self.restaurant_orders = RestaurantOrderRepository(session)
        self.restaurant_order_items = RestaurantOrderItemRepository(session)
