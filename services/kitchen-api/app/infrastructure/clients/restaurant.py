from typing import Any

import httpx
from pydantic import ValidationError

from app.modules.orders.schemas import RestaurantOrderResponse


class RestaurantTimeoutError(Exception):
    pass


class RestaurantCommunicationError(Exception):
    pass


class RestaurantClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client

    async def create_order(
        self,
        payload: dict[str, Any],
    ) -> RestaurantOrderResponse:
        try:
            response = await self.client.post(
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
