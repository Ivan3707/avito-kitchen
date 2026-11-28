from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_catalog_sync_service, get_order_service
from app.main import app
from app.modules.catalog.sync.schemas import SyncResponse
from app.modules.orders.schemas import RestaurantOrderResponse

pytestmark = pytest.mark.contract


def test_module_routes_dispatch_through_dependencies() -> None:
    class SyncService:
        async def sync(self):
            return SyncResponse(status="updated", snapshot_id=uuid4())

    class OrderService:
        async def create_order(self, order):
            assert order.order_id == "order-1"
            return RestaurantOrderResponse(
                accepted=True, restaurant_order_id=uuid4()
            )

    app.dependency_overrides[get_catalog_sync_service] = lambda: SyncService()
    app.dependency_overrides[get_order_service] = lambda: OrderService()
    try:
        with TestClient(app) as client:
            sync = client.post("/sync")
            order = client.post(
                "/orders",
                json={
                    "order_id": "order-1",
                    "branch_external_id": "branch-1",
                    "items": [
                        {
                            "menu_item_external_id": "item-1",
                            "quantity": 1,
                            "unit_price": 100,
                        }
                    ],
                },
            )
        assert sync.status_code == 200
        assert sync.json()["status"] == "updated"
        assert order.status_code == 200
        assert order.json()["accepted"] is True
    finally:
        app.dependency_overrides.clear()
