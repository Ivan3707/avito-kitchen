from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import NonEmptyString, StrictSchema


class OrderItem(StrictSchema):
    menu_item_external_id: NonEmptyString
    quantity: int = Field(ge=1)
    unit_price: int = Field(gt=0)


class RestaurantOrder(StrictSchema):
    order_id: NonEmptyString
    branch_external_id: NonEmptyString
    items: list[OrderItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_items(self) -> "RestaurantOrder":
        item_ids = [item.menu_item_external_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("menu item external_id values must be unique")
        return self


class BusinessErrorCode(StrEnum):
    BRANCH_UNAVAILABLE = "BRANCH_UNAVAILABLE"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_UNAVAILABLE = "PRODUCT_UNAVAILABLE"
    PRICE_CHANGED = "PRICE_CHANGED"
    ORDER_ID_CONFLICT = "ORDER_ID_CONFLICT"
    RESTAURANT_REJECTED = "RESTAURANT_REJECTED"


class ValidationIssue(StrictSchema):
    code: BusinessErrorCode
    message: NonEmptyString
    menu_item_external_id: NonEmptyString | None = None
    old_price: int | None = Field(default=None, gt=0)
    current_price: int | None = Field(default=None, gt=0)


class RestaurantOrderResponse(StrictSchema):
    accepted: bool
    restaurant_order_id: UUID | None = None
    reason: ValidationIssue | None = None

    @model_validator(mode="after")
    def validate_result(self) -> "RestaurantOrderResponse":
        if self.accepted and (
            self.restaurant_order_id is None or self.reason is not None
        ):
            raise ValueError("accepted order requires id and no reason")
        if not self.accepted and (
            self.restaurant_order_id is not None or self.reason is None
        ):
            raise ValueError("rejected order requires reason and no id")
        return self
