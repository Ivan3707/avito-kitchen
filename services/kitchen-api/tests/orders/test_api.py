from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_order_service
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.catalog.sync.schemas import SyncPayload
from app.modules.catalog.sync.service import SyncService
from app.modules.orders.ports import RestaurantOrderCommand
from app.modules.orders.router import router
from app.modules.orders.schemas import RestaurantOrderResponse
from app.modules.orders.service import OrderService
from app.modules.users.models.user import User

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_order_contract(test_session_factory):
    restaurant_id = f"restaurant-{uuid4()}"
    branch_id = f"branch-{uuid4()}"
    user_email = f"customer-{uuid4()}@example.com"
    payload = SyncPayload.model_validate(
        {
            "snapshot_id": uuid4(),
            "schema_version": 3,
            "catalog_revision": 0,
            "generated_at": datetime.now(UTC),
            "restaurant": {
                "external_id": restaurant_id,
                "name": "Restaurant",
                "description": None,
            },
            "branches": [
                {
                    "external_id": branch_id,
                    "name": "Branch",
                    "address": "Address",
                    "is_active": True,
                    "is_accepting_orders": True,
                }
            ],
            "menu": {
                "external_id": "menu-1",
                "name": "Menu",
                "items": [
                    {
                        "external_id": "item-1",
                        "name": "Item",
                        "description": None,
                        "is_active": True,
                    }
                ],
            },
            "availability": [
                {
                    "branch_external_id": branch_id,
                    "items": [
                        {
                            "menu_item_external_id": "item-1",
                            "is_available": True,
                            "price": 100,
                        }
                    ],
                }
            ],
        }
    )

    def factory():
        return UnitOfWork(test_session_factory)

    async with factory() as uow:
        await SyncService(factory).sync(uow, payload)
        uow.users.users.add(
            User(email=user_email, password_hash="test-password-hash")
        )

    class FakeRestaurantClient:
        async def create_order(self, order: RestaurantOrderCommand):
            return RestaurantOrderResponse(
                accepted=True, restaurant_order_id="restaurant-order-1"
            )

    service = OrderService(factory, FakeRestaurantClient())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_order_service] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/integration/v1/orders",
            headers={"X-User-Email": user_email},
            json={
                "order_id": "order-1",
                "restaurant_external_id": restaurant_id,
                "branch_external_id": branch_id,
                "items": [
                    {
                        "menu_item_external_id": "item-1",
                        "quantity": 1,
                        "unit_price": 100,
                    }
                ],
            },
        )
    assert response.status_code == 200
    assert response.json()["accepted"] is True
