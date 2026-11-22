from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.lifespan import lifespan
from app.infrastructure.clients.kitchen import (
    KitchenCommunicationError,
    KitchenTimeoutError,
)
from app.schemas import RestaurantOrder, RestaurantOrderResponse, SyncResponse

app = FastAPI(
    title="Demo Restaurant",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(KitchenTimeoutError)
async def kitchen_timeout(
    request: Request, exc: KitchenTimeoutError
) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={"detail": "Kitchen synchronization timed out"},
    )


@app.exception_handler(KitchenCommunicationError)
async def kitchen_communication_error(
    request: Request, exc: KitchenCommunicationError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "Kitchen synchronization failed"},
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
) -> RestaurantOrderResponse:
    service = request.app.state.service

    return await service.create_order(order)
