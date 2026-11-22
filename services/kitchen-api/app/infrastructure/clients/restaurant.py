from typing import Any

import httpx
from pydantic import ValidationError

from app.integration.schemas.orders import RestaurantOrderResponse


class RestaurantTimeoutError(Exception):
    pass


class RestaurantCommunicationError(Exception):
    pass


class RestaurantClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def create_order(
        self,
        payload: dict[str, Any],
    ) -> RestaurantOrderResponse:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders",
                    json=payload,
                    timeout=5.0,
                )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise RestaurantTimeoutError from exc

        try:
            response.raise_for_status()
            return RestaurantOrderResponse.model_validate(response.json())
        except (httpx.HTTPStatusError, ValueError, ValidationError) as exc:
            raise RestaurantCommunicationError from exc
