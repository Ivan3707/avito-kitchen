import httpx

from app.schemas import RestaurantOrder, SyncResponse


class DemoRestaurantService:
    def __init__(self) -> None:
        self.orders: dict[str, str] = {}
        self.sync_version = 0

    def create_order(self, order: RestaurantOrder) -> str:
        if order.order_id in self.orders:
            return self.orders[order.order_id]

        if order.branch_external_id != "demo-branch":
            raise ValueError("Unknown branch")

        for item in order.items:
            if item.menu_item_external_id != "burger":
                raise ValueError("Unknown product")

            if item.unit_price != 500:
                raise ValueError("Price changed")

        from uuid import uuid4

        restaurant_order_id = str(uuid4())
        self.orders[order.order_id] = restaurant_order_id

        return restaurant_order_id

    async def sync(self) -> SyncResponse:
        self.sync_version += 1

        payload = {
            "version": self.sync_version,
            "restaurant": {
                "external_id": "demo-restaurant",
                "name": "Demo Restaurant",
                "description": "Demo restaurant for integration testing",
            },
            "branches": [
                {
                    "external_id": "demo-branch",
                    "name": "Demo Branch",
                    "address": "Demo address",
                    "is_active": True,
                    "is_accepting_orders": True,
                }
            ],
            "menu": {
                "external_id": "demo-menu",
                "name": "Demo Menu",
                "items": [
                    {
                        "external_id": "burger",
                        "name": "Burger",
                        "description": "Demo burger",
                        "price": 500,
                        "is_active": True,
                    }
                ],
            },
            "availability": [
                {
                    "branch_external_id": "demo-branch",
                    "items": [
                        {
                            "menu_item_external_id": "burger",
                            "is_available": True,
                        }
                    ],
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://kitchen-api:8000/integration/v1/sync",
                json=payload,
            )

        response.raise_for_status()

        return SyncResponse(**response.json())


service = DemoRestaurantService()
