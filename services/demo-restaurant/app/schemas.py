from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    menu_item_external_id: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_price: int = Field(gt=0)


class RestaurantOrder(BaseModel):
    order_id: str = Field(min_length=1)
    branch_external_id: str = Field(min_length=1)
    items: list[OrderItem] = Field(min_length=1)


class SyncResponse(BaseModel):
    status: str
    version: int
    reason: str | None = None
