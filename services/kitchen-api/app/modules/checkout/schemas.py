from uuid import UUID

from pydantic import BaseModel

from app.core.schemas import NonEmptyString


class CheckoutRequest(BaseModel):
    order_id: NonEmptyString


class CheckoutResponse(BaseModel):
    accepted: bool
    order_id: UUID | None = None
    restaurant_order_id: NonEmptyString | None = None
    reason: str | None = None
