from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_order_service
from app.modules.orders.schemas import RestaurantOrder, RestaurantOrderResponse
from app.modules.orders.service import OrderService

router = APIRouter()


@router.post("/orders")
async def create_order(
    order: RestaurantOrder,
    service: Annotated[OrderService, Depends(get_order_service)],
) -> RestaurantOrderResponse:
    return await service.create_order(order)
