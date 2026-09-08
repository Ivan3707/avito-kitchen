from fastapi import FastAPI

from app.schemas import RestaurantOrder, SyncResponse
from app.service import service

app = FastAPI(
    title="Demo Restaurant",
    version="1.0.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sync")
async def sync() -> SyncResponse:
    return await service.sync()


@app.post("/orders")
async def create_order(
    order: RestaurantOrder,
) -> dict[str, str | bool]:
    try:
        restaurant_order_id = service.create_order(order)
    except ValueError as exc:
        return {
            "accepted": False,
            "reason": str(exc),
        }

    return {
        "accepted": True,
        "restaurant_order_id": restaurant_order_id,
    }
