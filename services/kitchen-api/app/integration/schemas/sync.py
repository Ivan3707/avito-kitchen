from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from .common import NonEmptyString, SyncStatus


class RestaurantSync(BaseModel):
    external_id: NonEmptyString
    name: NonEmptyString
    description: str | None


class BranchSync(BaseModel):
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


class MenuItemSync(BaseModel):
    external_id: NonEmptyString
    name: NonEmptyString
    description: str | None
    price: int = Field(gt=0)
    is_active: bool


class MenuSync(BaseModel):
    external_id: NonEmptyString
    name: NonEmptyString
    items: list[MenuItemSync]

    @model_validator(mode="after")
    def validate_unique_items(self) -> "MenuSync":
        external_ids = [item.external_id for item in self.items]

        if len(external_ids) != len(set(external_ids)):
            raise ValueError("menu item external_id values must be unique")

        return self


class MenuItemAvailabilitySync(BaseModel):
    menu_item_external_id: NonEmptyString
    is_available: bool


class BranchAvailabilitySync(BaseModel):
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


class SyncPayload(BaseModel):
    version: int = Field(ge=1)
    restaurant: RestaurantSync
    branches: list[BranchSync] = Field(min_length=1)
    menu: MenuSync
    availability: list[BranchAvailabilitySync] = Field(min_length=1)

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

        return self


class UpdatedSyncResponse(BaseModel):
    status: Literal["updated"] = SyncStatus.UPDATED
    version: int = Field(ge=1)


class IgnoredSyncResponse(BaseModel):
    status: Literal["ignored"] = SyncStatus.IGNORED
    version: int = Field(ge=1)

SyncResponse = Annotated[
    UpdatedSyncResponse | IgnoredSyncResponse,
    Field(discriminator="status"),
]
