from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.core.dependencies import get_cart_service
from app.modules.cart.schemas import (
    AddCartItemRequest,
    CartResponse,
    UpdateCartItemRequest,
)
from app.modules.cart.service import CartService

router = APIRouter(prefix="/api/v1", tags=["cart"])


@router.get("/branches/{branch_id}/cart", response_model=CartResponse)
async def get_cart(
    branch_id: UUID,
    x_user_email: str = Header(...),
    service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await service.get_cart_by_email(x_user_email, branch_id)


@router.post("/branches/{branch_id}/cart/items", response_model=CartResponse)
async def add_cart_item(
    branch_id: UUID,
    request: AddCartItemRequest,
    x_user_email: str = Header(...),
    service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await service.add_item_by_email(x_user_email, branch_id, request)


@router.patch(
    "/branches/{branch_id}/cart/items/{menu_item_id}",
    response_model=CartResponse,
)
async def update_cart_item(
    branch_id: UUID,
    menu_item_id: UUID,
    request: UpdateCartItemRequest,
    x_user_email: str = Header(...),
    service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await service.update_item_by_email(
        x_user_email, branch_id, menu_item_id, request
    )


@router.delete(
    "/branches/{branch_id}/cart/items/{menu_item_id}",
    response_model=CartResponse,
)
async def remove_cart_item(
    branch_id: UUID,
    menu_item_id: UUID,
    x_user_email: str = Header(...),
    service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await service.remove_item_by_email(
        x_user_email, branch_id, menu_item_id
    )
