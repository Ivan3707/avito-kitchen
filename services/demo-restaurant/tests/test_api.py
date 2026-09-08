import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_order() -> None:
    response = client.post(
        "/orders",
        json={
            "order_id": "api-order-1",
            "branch_external_id": "demo-branch",
            "items": [
                {
                    "menu_item_external_id": "burger",
                    "quantity": 2,
                    "unit_price": 500,
                }
            ],
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["accepted"] is True
    assert data["restaurant_order_id"]


def test_create_order_is_idempotent() -> None:
    order = {
        "order_id": "api-idempotent-order",
        "branch_external_id": "demo-branch",
        "items": [
            {
                "menu_item_external_id": "burger",
                "quantity": 1,
                "unit_price": 500,
            }
        ],
    }

    first_response = client.post("/orders", json=order)
    second_response = client.post("/orders", json=order)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_id = first_response.json()["restaurant_order_id"]
    second_id = second_response.json()["restaurant_order_id"]

    assert first_id == second_id
