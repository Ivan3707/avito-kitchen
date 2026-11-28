from fastapi import APIRouter, Depends, Header

from app.core.dependencies import get_order_service
from app.modules.orders.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderValidationRequest,
    OrderValidationResponse,
)
from app.modules.orders.service import OrderService

router = APIRouter(prefix="/integration/v1", tags=["integration"])


@router.post("/orders/validate", response_model=OrderValidationResponse)
async def validate_order(
    payload: OrderValidationRequest,
    service: OrderService = Depends(get_order_service),
) -> OrderValidationResponse:
    return await service.validate(payload)


@router.post("/orders", response_model=CreateOrderResponse)
async def create_order(
    payload: CreateOrderRequest,
    x_user_email: str = Header(...),
    service: OrderService = Depends(get_order_service),
) -> CreateOrderResponse:
    return await service.create_order(request=payload, user_email=x_user_email)
