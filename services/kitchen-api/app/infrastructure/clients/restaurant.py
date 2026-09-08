from typing import Any

import httpx


class RestaurantTimeoutError(Exception):
    pass


class RestaurantClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def create_order(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders",
                    json=payload,
                    timeout=5.0,
                )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise RestaurantTimeoutError from exc

        response.raise_for_status()

        return response.json()
