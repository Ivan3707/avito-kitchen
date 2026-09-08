import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import RestaurantOrder
from app.service import DemoRestaurantService


def test_create_order_returns_restaurant_order_id() -> None:
    service = DemoRestaurantService()

    order = RestaurantOrder(
        order_id="order-1",
        branch_external_id="demo-branch",
        items=[
            {
                "menu_item_external_id": "burger",
                "quantity": 2,
                "unit_price": 500,
            }
        ],
    )

    restaurant_order_id = service.create_order(order)

    assert restaurant_order_id


def test_create_order_is_idempotent() -> None:
    service = DemoRestaurantService()

    order = RestaurantOrder(
        order_id="order-1",
        branch_external_id="demo-branch",
        items=[
            {
                "menu_item_external_id": "burger",
                "quantity": 2,
                "unit_price": 500,
            }
        ],
    )

    first_id = service.create_order(order)
    second_id = service.create_order(order)

    assert first_id == second_id
    assert len(service.orders) == 1
