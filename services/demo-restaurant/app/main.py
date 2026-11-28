from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.lifespan import lifespan
from app.infrastructure.clients.kitchen import (
    KitchenCommunicationError,
    KitchenTimeoutError,
)
from app.infrastructure.database import models  # noqa: F401
from app.modules.catalog.sync.router import router as catalog_sync_router
from app.modules.orders.router import router as orders_router

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


app.include_router(catalog_sync_router)
app.include_router(orders_router)
