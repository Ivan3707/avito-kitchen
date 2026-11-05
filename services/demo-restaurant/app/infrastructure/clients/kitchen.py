from typing import Any

import httpx


class KitchenTimeoutError(Exception):
    pass


class KitchenClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self.client = client
        self.base_url = base_url.rstrip("/")

    async def sync_order(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await self.client.post(
                f"{self.base_url}/integration/v1/sync",
                json=payload,
                timeout=5.0,
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise KitchenTimeoutError from exc

        response.raise_for_status()

        return response.json()
