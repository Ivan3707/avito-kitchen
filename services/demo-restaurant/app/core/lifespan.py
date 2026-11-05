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
from app.service.service import DemoRestaurantService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient() as http_client:
        kitchen_client = KitchenClient(
            client=http_client,
            base_url=settings.kitchen_api_url,
        )

        app.state.service = DemoRestaurantService(
            session_factory=async_session_maker,
            kitchen_client=kitchen_client,
        )

        try:
            yield
        finally:
            await engine.dispose()