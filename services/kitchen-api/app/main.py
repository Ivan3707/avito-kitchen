from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.cart import router as cart_router
from app.api.catalog import router as catalog_router
from app.api.integration import router as integration_router
from app.services.errors import ConflictError, ResourceNotFoundError

app = FastAPI(
    title="Avito Kitchen",
    version="1.0.0",
)

app.include_router(catalog_router)
app.include_router(integration_router)
app.include_router(cart_router)


@app.exception_handler(ResourceNotFoundError)
async def handle_not_found(
    request: Request, exc: ResourceNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def handle_conflict(
    request: Request, exc: ConflictError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})
