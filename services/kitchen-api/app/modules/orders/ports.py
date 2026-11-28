from dataclasses import dataclass
from typing import Protocol

from app.modules.orders.schemas import RestaurantOrderResponse


@dataclass(frozen=True)
class RestaurantOrderItemCommand:
    menu_item_external_id: str
    quantity: int
    unit_price: int


@dataclass(frozen=True)
class RestaurantOrderCommand:
    order_id: str
    branch_external_id: str
    items: tuple[RestaurantOrderItemCommand, ...]


class RestaurantOrderGateway(Protocol):
    async def create_order(
        self, order: RestaurantOrderCommand
    ) -> RestaurantOrderResponse: ...
