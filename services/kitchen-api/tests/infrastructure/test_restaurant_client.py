import json

import httpx
import pytest

from app.infrastructure.clients.restaurant import RestaurantClient
from app.modules.orders.errors import (
    RestaurantCommunicationError,
    RestaurantTimeoutError,
)
from app.modules.orders.ports import (
    RestaurantOrderCommand,
    RestaurantOrderItemCommand,
)
from app.modules.orders.schemas import BusinessErrorCode

pytestmark = pytest.mark.unit


def command():
    return RestaurantOrderCommand(
        order_id="order-1",
        branch_external_id="branch-1",
        items=(
            RestaurantOrderItemCommand("item-1", 2, 100),
            RestaurantOrderItemCommand("item-2", 1, 200),
        ),
    )


@pytest.mark.asyncio
async def test_accepted_response_preserves_exact_request_and_item_order():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"accepted": True, "restaurant_order_id": "restaurant-1"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http:
        client = RestaurantClient("https://restaurant.example/", http)
        response = await client.create_order(command())

    assert response.accepted is True
    assert response.restaurant_order_id == "restaurant-1"
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url == "https://restaurant.example/orders"
    assert requests[0].extensions["timeout"] == {
        "connect": 5.0,
        "read": 5.0,
        "write": 5.0,
        "pool": 5.0,
    }
    assert json.loads(requests[0].content) == {
        "order_id": "order-1",
        "branch_external_id": "branch-1",
        "items": [
            {
                "menu_item_external_id": "item-1",
                "quantity": 2,
                "unit_price": 100,
            },
            {
                "menu_item_external_id": "item-2",
                "quantity": 1,
                "unit_price": 200,
            },
        ],
    }


@pytest.mark.asyncio
async def test_business_rejection_preserves_reason_details():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "accepted": False,
                "reason": {
                    "code": "PRICE_CHANGED",
                    "message": "Product price has changed",
                    "menu_item_external_id": "item-1",
                    "old_price": 100,
                    "current_price": 120,
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http:
        response = await RestaurantClient(
            "https://restaurant.example", http
        ).create_order(command())

    assert response.accepted is False
    assert response.reason.code == BusinessErrorCode.PRICE_CHANGED
    assert response.reason.menu_item_external_id == "item-1"
    assert response.reason.old_price == 100
    assert response.reason.current_price == 120


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("timeout"), httpx.ConnectError("connect")]
)
async def test_timeout_and_connect_error_become_unknown_result(error):
    def handler(request):
        raise error

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http:
        with pytest.raises(RestaurantTimeoutError):
            await RestaurantClient(
                "https://restaurant.example", http
            ).create_order(command())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, json={"message": "unavailable"}),
        httpx.Response(200, text="{invalid-json"),
        httpx.Response(200, json={"accepted": True}),
    ],
)
async def test_http_json_and_validation_failures_become_communication_error(
    response,
):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as http:
        with pytest.raises(RestaurantCommunicationError):
            await RestaurantClient(
                "https://restaurant.example", http
            ).create_order(command())
