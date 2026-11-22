from app.infrastructure.database.models.order_item import OrderItem
from app.infrastructure.repositories.base import BaseRepository


class OrderItemRepository(BaseRepository[OrderItem]):
    model = OrderItem
