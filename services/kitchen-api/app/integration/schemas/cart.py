from uuid import UUID

from pydantic import BaseModel, Field

from .common import NonEmptyString


class AddCartItemRequest(BaseModel):
    menu_item_id: UUID
    quantity: int = Field(ge=1)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1)


class CartItemResponse(BaseModel):
    menu_item_id: UUID
    menu_item_external_id: NonEmptyString
    name: NonEmptyString
    price: int = Field(gt=0)
    quantity: int = Field(ge=1)
    is_available: bool


class CartResponse(BaseModel):
    id: UUID | None
    branch_id: UUID
    items: list[CartItemResponse]


class CheckoutRequest(BaseModel):
    order_id: NonEmptyString


class CheckoutResponse(BaseModel):
    accepted: bool
    order_id: UUID | None = None
    restaurant_order_id: NonEmptyString | None = None
    reason: str | None = None
