from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .common import NonEmptyString, SyncStatus


class SyncSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RestaurantSync(SyncSchema):
    external_id: NonEmptyString
    name: NonEmptyString
    description: str | None


class BranchSync(SyncSchema):
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


class MenuItemSync(SyncSchema):
    external_id: NonEmptyString
    name: NonEmptyString
    description: str | None
    price: int = Field(gt=0)
    is_active: bool


class MenuSync(SyncSchema):
    external_id: NonEmptyString
    name: NonEmptyString
    items: list[MenuItemSync]

    @model_validator(mode="after")
    def validate_unique_items(self) -> "MenuSync":
        external_ids = [item.external_id for item in self.items]

        if len(external_ids) != len(set(external_ids)):
            raise ValueError("menu item external_id values must be unique")

        return self


class MenuItemAvailabilitySync(SyncSchema):
    menu_item_external_id: NonEmptyString
    is_available: bool


class BranchAvailabilitySync(SyncSchema):
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


class SyncPayload(SyncSchema):
    snapshot_id: UUID
    schema_version: Literal[1]
    generated_at: datetime

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
        branch_ids = [branch.external_id for branch in self.branches]

        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError("branch external_id values must be unique")

        branch_ids_set = set(branch_ids)

        availability_branch_ids = [
            item.branch_external_id for item in self.availability
        ]

        if len(availability_branch_ids) != len(set(availability_branch_ids)):
            raise ValueError(
                "each branch must have exactly one availability entry"
            )

        if set(availability_branch_ids) != branch_ids_set:
            raise ValueError(
                "availability must contain every branch exactly once"
            )

        menu_item_ids = {item.external_id for item in self.menu.items}
        active_menu_items = {
            item.external_id: item.is_active for item in self.menu.items
        }
        active_branches = {
            branch.external_id: branch.is_active for branch in self.branches
        }

        for branch_availability in self.availability:
            if branch_availability.branch_external_id not in branch_ids_set:
                raise ValueError("availability references unknown branch")

            availability_item_ids = {
                item.menu_item_external_id
                for item in branch_availability.items
            }

            if availability_item_ids != menu_item_ids:
                raise ValueError(
                    "availability must contain every menu item "
                    "for every branch exactly once"
                )

            for item in branch_availability.items:
                if (
                    item.is_available
                    and not active_branches[
                        branch_availability.branch_external_id
                    ]
                ):
                    raise ValueError(
                        "inactive branch cannot have available menu items"
                    )
                if (
                    item.is_available
                    and not active_menu_items[item.menu_item_external_id]
                ):
                    raise ValueError(
                        "inactive menu item cannot be available in any branch"
                    )

        return self


class UpdatedSyncResponse(BaseModel):
    status: Literal["updated"] = SyncStatus.UPDATED
    snapshot_id: UUID


class IgnoredSyncResponse(BaseModel):
    status: Literal["ignored"] = SyncStatus.IGNORED
    snapshot_id: UUID
    reason: Literal["DUPLICATE_SNAPSHOT", "STALE_SNAPSHOT"]


SyncResponse = Annotated[
    UpdatedSyncResponse | IgnoredSyncResponse,
    Field(discriminator="status"),
]
