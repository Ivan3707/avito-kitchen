from fastapi import FastAPI, Request

from app.schemas import RestaurantOrder, SyncResponse

from app.core.lifespan import lifespan


app = FastAPI(
    title="Demo Restaurant",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sync")
async def sync(request: Request) -> SyncResponse:
    service = request.app.state.service
    return await service.sync()


@app.post("/orders")
async def create_order(
    order: RestaurantOrder,
    request: Request,
) -> dict[str, str | bool]:
    service = request.app.state.service

    try:
        restaurant_order_id = await service.create_order(order)
    except ValueError as exc:
        return {
            "accepted": False,
            "reason": str(exc),
        }

    return {
        "accepted": True,
        "restaurant_order_id": restaurant_order_id,
    }