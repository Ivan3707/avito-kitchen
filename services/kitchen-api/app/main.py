from fastapi import FastAPI

from app.api.cart import router as cart_router
from app.api.catalog import router as catalog_router
from app.api.integration import router as integration_router

app = FastAPI(
    title="Avito Kitchen",
    version="1.0.0",
)

app.include_router(catalog_router)
app.include_router(integration_router)
app.include_router(cart_router)
