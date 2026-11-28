from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.core.config import settings
from app.infrastructure.clients.kitchen import KitchenClient
from app.infrastructure.database.session import (
    async_session_maker,
    engine,
)
from app.modules.catalog.sync.service import CatalogSyncService
from app.modules.orders.service import OrderService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient() as http_client:
        kitchen_client = KitchenClient(
            client=http_client,
            base_url=settings.kitchen_api_url,
        )

        app.state.catalog_sync_service = CatalogSyncService(
            session_factory=async_session_maker,
            kitchen_client=kitchen_client,
        )

        app.state.order_service = OrderService(
            session_factory=async_session_maker,
        )

        try:
            yield
        finally:
            await engine.dispose()
