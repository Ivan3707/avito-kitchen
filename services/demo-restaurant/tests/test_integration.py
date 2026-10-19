import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

from app.service import DemoRestaurantService


@pytest.mark.asyncio
async def test_sync_sends_data_to_kitchen_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = DemoRestaurantService()

    class MockResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {
                "status": "updated",
                "version": 1,
            }

    async def mock_post(
        self: httpx.AsyncClient,
        url: str,
        **kwargs: object,
    ) -> MockResponse:
        assert url == "http://kitchen-api:8000/integration/v1/sync"

        payload = kwargs["json"]

        assert isinstance(payload, dict)
        assert payload["version"] == 1
        assert payload["restaurant"]["external_id"] == "demo-restaurant"
        assert payload["branches"][0]["external_id"] == "demo-branch"
        assert payload["menu"]["items"][0]["external_id"] == "burger"

        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    response = await service.sync()

    assert response.status == "updated"
    assert response.version == 1
    assert service.sync_version == 1
