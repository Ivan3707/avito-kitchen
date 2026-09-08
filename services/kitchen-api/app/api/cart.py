from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.infrastructure.database.session import async_session_maker
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.cart import (
    AddCartItemRequest,
    CartResponse,
    CheckoutRequest,
    CheckoutResponse,
    UpdateCartItemRequest,
)
from app.services.cart import CartService

router = APIRouter(
    prefix="/api/v1",
    tags=["cart"],
)


def get_uow() -> UnitOfWork:
    return UnitOfWork(async_session_maker)


@router.get(
    "/branches/{branch_id}/cart",
    response_model=CartResponse,
)
async def get_cart(
    branch_id: UUID,
    x_user_email: str = Header(...),
    uow: UnitOfWork = Depends(get_uow),
) -> CartResponse:
    service = CartService()

    async with uow:
        customer = await uow.customers.get_by_email(x_user_email)

        if customer is None:
            from app.infrastructure.database.models.customer import Customer

            customer = uow.customers.add(Customer(email=x_user_email))
            await uow.session.flush()

        return await service.get_cart(
            uow=uow,
            customer_id=customer.id,
            branch_id=branch_id,
        )


@router.post(
    "/branches/{branch_id}/cart/items",
    response_model=CartResponse,
)
async def add_cart_item(
    branch_id: UUID,
    request: AddCartItemRequest,
    x_user_email: str = Header(...),
    uow: UnitOfWork = Depends(get_uow),
) -> CartResponse:
    service = CartService()

    async with uow:
        customer = await uow.customers.get_by_email(x_user_email)

        if customer is None:
            from app.infrastructure.database.models.customer import Customer

            customer = uow.customers.add(Customer(email=x_user_email))
            await uow.session.flush()

        return await service.add_item(
            uow=uow,
            customer_id=customer.id,
            branch_id=branch_id,
            request=request,
        )


@router.patch(
    "/branches/{branch_id}/cart/items/{menu_item_id}",
    response_model=CartResponse,
)
async def update_cart_item(
    branch_id: UUID,
    menu_item_id: UUID,
    request: UpdateCartItemRequest,
    x_user_email: str = Header(...),
    uow: UnitOfWork = Depends(get_uow),
) -> CartResponse:
    service = CartService()

    async with uow:
        customer = await uow.customers.get_by_email(x_user_email)

        if customer is None:
            raise ValueError("Customer not found")

        return await service.update_item(
            uow=uow,
            customer_id=customer.id,
            branch_id=branch_id,
            menu_item_id=menu_item_id,
            request=request,
        )


@router.delete(
    "/branches/{branch_id}/cart/items/{menu_item_id}",
    response_model=CartResponse,
)
async def remove_cart_item(
    branch_id: UUID,
    menu_item_id: UUID,
    x_user_email: str = Header(...),
    uow: UnitOfWork = Depends(get_uow),
) -> CartResponse:
    service = CartService()

    async with uow:
        customer = await uow.customers.get_by_email(x_user_email)

        if customer is None:
            raise ValueError("Customer not found")

        return await service.remove_item(
            uow=uow,
            customer_id=customer.id,
            branch_id=branch_id,
            menu_item_id=menu_item_id,
        )


@router.post(
    "/branches/{branch_id}/cart/checkout",
    response_model=CheckoutResponse,
)
async def checkout_cart(
    branch_id: UUID,
    request: CheckoutRequest,
    x_user_email: str = Header(...),
    uow: UnitOfWork = Depends(get_uow),
) -> CheckoutResponse:
    service = CartService()

    async with uow:
        customer = await uow.customers.get_by_email(x_user_email)

        if customer is None:
            raise ValueError("Customer not found")

        return await service.checkout(
            uow=uow,
            customer_id=customer.id,
            customer_email=x_user_email,
            branch_id=branch_id,
            request=request,
        )
