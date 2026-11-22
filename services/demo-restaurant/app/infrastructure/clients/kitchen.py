from typing import Any

import httpx


class KitchenTimeoutError(Exception):
    pass


class KitchenCommunicationError(Exception):
    pass


class KitchenClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self.client = client
        self.base_url = base_url.rstrip("/")

    async def sync_catalog(
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

        try:
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise KitchenCommunicationError from exc
        if not isinstance(result, dict):
            raise KitchenCommunicationError("Kitchen returned a non-object")
        return result
