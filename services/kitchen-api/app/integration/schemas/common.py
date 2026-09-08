from enum import StrEnum
from typing import Annotated

from pydantic import Field

NonEmptyString = Annotated[str, Field(min_length=1)]


class SyncStatus(StrEnum):
    UPDATED = "updated"
    IGNORED = "ignored"


class BusinessErrorCode(StrEnum):
    BRANCH_UNAVAILABLE = "BRANCH_UNAVAILABLE"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_UNAVAILABLE = "PRODUCT_UNAVAILABLE"
    INSUFFICIENT_QUANTITY = "INSUFFICIENT_QUANTITY"
    PRICE_CHANGED = "PRICE_CHANGED"
    RESTAURANT_TIMEOUT = "RESTAURANT_TIMEOUT"
    ORDER_ID_CONFLICT = "ORDER_ID_CONFLICT"
