from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import NonEmptyString


class RestaurantResponse(BaseModel):
    id: UUID
    name: NonEmptyString
    description: str | None


class BranchResponse(BaseModel):
    id: UUID
    name: NonEmptyString
    address: NonEmptyString
    is_active: bool
    is_accepting_orders: bool


class MenuItemResponse(BaseModel):
    id: UUID
    external_id: NonEmptyString
    name: NonEmptyString
    description: str | None
    price: int | None = Field(gt=0)
    is_available: bool


class BranchMenuResponse(BaseModel):
    branch_id: UUID
    items: list[MenuItemResponse]
