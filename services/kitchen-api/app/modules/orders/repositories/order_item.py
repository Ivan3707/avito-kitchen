from app.infrastructure.repositories.base import BaseRepository
from app.modules.orders.models.order_item import OrderItem


class OrderItemRepository(BaseRepository[OrderItem]):
    model = OrderItem
