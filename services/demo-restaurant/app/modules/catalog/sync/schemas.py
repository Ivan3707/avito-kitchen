from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.schemas import NonEmptyString, StrictSchema


class SyncResponse(StrictSchema):
    status: Literal["updated", "ignored"]
    snapshot_id: UUID
    reason: (
        Literal[
            "DUPLICATE_SNAPSHOT",
            "DUPLICATE_STATE",
            "STALE_SNAPSHOT",
        ]
        | None
    ) = None


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
    schema_version: Literal[3]
    catalog_revision: int = Field(ge=0)
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
