from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.core.dependencies import get_checkout_service
from app.modules.checkout.schemas import CheckoutRequest, CheckoutResponse
from app.modules.checkout.service import CheckoutService

router = APIRouter(prefix="/api/v1", tags=["cart"])


@router.post(
    "/branches/{branch_id}/cart/checkout", response_model=CheckoutResponse
)
async def checkout_cart(
    branch_id: UUID,
    request: CheckoutRequest,
    x_user_email: str = Header(...),
    service: CheckoutService = Depends(get_checkout_service),
) -> CheckoutResponse:
    return await service.checkout(
        user_email=x_user_email, branch_id=branch_id, request=request
    )
