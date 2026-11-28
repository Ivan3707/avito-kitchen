from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import NonEmptyString


class BusinessErrorCode(StrEnum):
    BRANCH_UNAVAILABLE = "BRANCH_UNAVAILABLE"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_UNAVAILABLE = "PRODUCT_UNAVAILABLE"
    INSUFFICIENT_QUANTITY = "INSUFFICIENT_QUANTITY"
    PRICE_CHANGED = "PRICE_CHANGED"
    RESTAURANT_TIMEOUT = "RESTAURANT_TIMEOUT"
    RESTAURANT_REJECTED = "RESTAURANT_REJECTED"
    ORDER_ID_CONFLICT = "ORDER_ID_CONFLICT"


class OrderItemRequest(BaseModel):
    menu_item_external_id: NonEmptyString
    quantity: int = Field(ge=1)
    unit_price: int = Field(gt=0)


class OrderValidationRequest(BaseModel):
    restaurant_external_id: NonEmptyString
    branch_external_id: NonEmptyString
    items: list[OrderItemRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_items(self) -> "OrderValidationRequest":
        item_ids = [item.menu_item_external_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("menu item external_id values must be unique")
        return self


class ValidationIssue(BaseModel):
    code: BusinessErrorCode
    message: NonEmptyString
    menu_item_external_id: NonEmptyString | None = None
    old_price: int | None = Field(default=None, gt=0)
    current_price: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_fields_by_code(self) -> "ValidationIssue":
        if self.code == BusinessErrorCode.BRANCH_UNAVAILABLE:
            if (
                self.menu_item_external_id is not None
                or self.old_price is not None
                or self.current_price is not None
            ):
                raise ValueError(
                    "branch availability issue cannot contain "
                    "product or price fields"
                )

        elif self.code in {
            BusinessErrorCode.PRODUCT_NOT_FOUND,
            BusinessErrorCode.PRODUCT_UNAVAILABLE,
            BusinessErrorCode.INSUFFICIENT_QUANTITY,
        }:
            if self.menu_item_external_id is None:
                raise ValueError(
                    "product issue requires menu_item_external_id"
                )

            if self.old_price is not None or self.current_price is not None:
                raise ValueError(
                    "non-price product issue cannot contain price fields"
                )

        elif self.code == BusinessErrorCode.PRICE_CHANGED:
            if self.menu_item_external_id is None:
                raise ValueError(
                    "price change issue requires menu_item_external_id"
                )

            if self.old_price is None:
                raise ValueError("price change issue requires old_price")

            if self.current_price is None:
                raise ValueError("price change issue requires current_price")

        return self


class OrderValidationResponse(BaseModel):
    valid: bool
    issues: list[ValidationIssue]

    @model_validator(mode="after")
    def validate_consistency(self) -> "OrderValidationResponse":
        if self.valid and self.issues:
            raise ValueError("valid response cannot contain issues")

        if not self.valid and not self.issues:
            raise ValueError(
                "invalid response must contain at least one issue"
            )

        return self


class CreateOrderRequest(BaseModel):
    order_id: NonEmptyString
    restaurant_external_id: NonEmptyString
    branch_external_id: NonEmptyString
    items: list[OrderItemRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_items(self) -> "CreateOrderRequest":
        item_ids = [item.menu_item_external_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("menu item external_id values must be unique")
        return self


class CreateOrderResponse(BaseModel):
    accepted: bool
    order_id: UUID | None = None
    restaurant_order_id: NonEmptyString | None = None
    reason: ValidationIssue | None = None

    @model_validator(mode="after")
    def validate_result(self) -> "CreateOrderResponse":
        if self.accepted:
            if self.restaurant_order_id is None:
                raise ValueError(
                    "accepted response requires restaurant_order_id"
                )

            if self.reason is not None:
                raise ValueError("accepted response cannot contain reason")

        else:
            if self.reason is None:
                raise ValueError("rejected response requires reason")

            if self.restaurant_order_id is not None:
                raise ValueError(
                    "rejected response cannot contain restaurant_order_id"
                )

        return self


class RestaurantOrderResponse(BaseModel):
    accepted: bool
    restaurant_order_id: NonEmptyString | None = None
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
