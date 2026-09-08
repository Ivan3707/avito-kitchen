from fastapi import APIRouter, Depends, Header

from app.core.config import settings
from app.infrastructure.clients.restaurant import RestaurantClient
from app.infrastructure.database.session import async_session_maker
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.orders import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderValidationRequest,
    OrderValidationResponse,
)
from app.integration.schemas.sync import SyncPayload, SyncResponse
from app.services.order import OrderService
from app.services.sync import SyncService

router = APIRouter(
    prefix="/integration/v1",
    tags=["integration"],
)


def get_uow() -> UnitOfWork:
    return UnitOfWork(async_session_maker)


@router.post(
    "/sync",
    response_model=SyncResponse,
)
async def sync(
    payload: SyncPayload,
    uow: UnitOfWork = Depends(get_uow),
) -> SyncResponse:
    service = SyncService()

    async with uow:
        return await service.sync(
            uow=uow,
            payload=payload,
        )


@router.post(
    "/orders/validate",
    response_model=OrderValidationResponse,
)
async def validate_order(
    payload: OrderValidationRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> OrderValidationResponse:
    service = OrderService()

    async with uow:
        return await service.validate_order(
            uow=uow,
            request=payload,
        )


@router.post(
    "/orders",
    response_model=CreateOrderResponse,
)
async def create_order(
    payload: CreateOrderRequest,
    x_user_email: str = Header(...),
    uow: UnitOfWork = Depends(get_uow),
) -> CreateOrderResponse:
    service = OrderService()

    async with uow:
        return await service.create_order(
            uow=uow,
            request=payload,
            customer_email=x_user_email,
            restaurant_client=RestaurantClient(
                settings.DEMO_RESTAURANT_URL,
            ),
        )
