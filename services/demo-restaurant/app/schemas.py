from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

NonEmptyString = Annotated[str, Field(min_length=1)]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class SyncResponse(StrictSchema):
    status: Literal["updated", "ignored"]
    snapshot_id: UUID
    reason: Literal["DUPLICATE_SNAPSHOT", "STALE_SNAPSHOT"] | None = None


class RestaurantSync(StrictSchema):
    external_id: NonEmptyString
    name: NonEmptyString
    description: str | None


class BranchSync(StrictSchema):
    external_id: NonEmptyString
    name: NonEmptyString
    address: NonEmptyString
    is_active: bool
    is_accepting_orders: bool
    branch_version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order_acceptance(self) -> "BranchSync":
        if not self.is_active and self.is_accepting_orders:
            raise ValueError("inactive branch cannot accept orders")

        return self


class MenuItemSync(StrictSchema):
    external_id: NonEmptyString
    name: NonEmptyString
    description: str | None
    is_active: bool


class MenuSync(StrictSchema):
    external_id: NonEmptyString
    name: NonEmptyString
    items: list[MenuItemSync]

    @model_validator(mode="after")
    def validate_unique_items(self) -> "MenuSync":
        external_ids = [item.external_id for item in self.items]

        if len(external_ids) != len(set(external_ids)):
            raise ValueError("menu item external_id values must be unique")

        return self


class MenuItemAvailabilitySync(StrictSchema):
    menu_item_external_id: NonEmptyString
    is_available: bool
    price: int | None = Field(gt=0)

    @model_validator(mode="after")
    def validate_available_price(self) -> "MenuItemAvailabilitySync":
        if self.is_available and self.price is None:
            raise ValueError("available menu item requires a positive price")
        return self


class BranchAvailabilitySync(StrictSchema):
    branch_external_id: NonEmptyString
    items: list[MenuItemAvailabilitySync]

    @model_validator(mode="after")
    def validate_unique_items(self) -> "BranchAvailabilitySync":
        external_ids = [item.menu_item_external_id for item in self.items]

        if len(external_ids) != len(set(external_ids)):
            raise ValueError(
                "menu item external_id values must be unique "
                "within branch availability"
            )

        return self


class SyncPayload(StrictSchema):
    snapshot_id: UUID
    schema_version: Literal[2]
    generated_at: datetime = Field(
        ...,
        description="UTC timestamp when the snapshot was generated",
    )

    restaurant: RestaurantSync
    branches: list[BranchSync]
    menu: MenuSync
    availability: list[BranchAvailabilitySync]

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")

        return value

    @model_validator(mode="after")
    def validate_cross_references(self) -> "SyncPayload":
        branch_ids = {branch.external_id for branch in self.branches}

        if len(branch_ids) != len(self.branches):
            raise ValueError("branch external_id values must be unique")

        availability_branch_ids = {
            item.branch_external_id for item in self.availability
        }

        if len(availability_branch_ids) != len(self.availability):
            raise ValueError(
                "each branch must have exactly one availability entry"
            )

        if availability_branch_ids != branch_ids:
            raise ValueError(
                "availability must contain every branch exactly once"
            )

        menu_items = {
            item.external_id: item.is_active for item in self.menu.items
        }

        menu_item_ids = set(menu_items)

        for branch_availability in self.availability:
            availability_items = {
                item.menu_item_external_id: item.is_available
                for item in branch_availability.items
            }

            availability_item_ids = set(availability_items)

            branch_is_active = next(
                branch.is_active
                for branch in self.branches
                if branch.external_id == branch_availability.branch_external_id
            )

            if availability_item_ids != menu_item_ids:
                raise ValueError(
                    "availability must contain every menu item "
                    "for every branch exactly once"
                )

            for menu_item_id, is_available in availability_items.items():
                is_active = menu_items[menu_item_id]

                if not branch_is_active and is_available:
                    raise ValueError(
                        f"inactive branch {branch_availability.branch_external_id} "
                        "cannot have available menu items"
                    )

                if not is_active and is_available:
                    raise ValueError(
                        f"inactive menu item {menu_item_id} "
                        "cannot be available in any branch"
                    )

        return self
