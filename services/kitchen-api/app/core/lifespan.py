from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.core.config import settings
from app.core.rate_limit import InMemoryRateLimiter
from app.infrastructure.clients.email import EmailClient
from app.infrastructure.clients.restaurant import RestaurantClient
from app.infrastructure.database.session import async_session_maker, engine
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.auth.registration import RegistrationService
from app.modules.cart.service import CartService
from app.modules.catalog.service import CatalogService
from app.modules.catalog.sync.service import SyncService
from app.modules.checkout.service import CheckoutService
from app.modules.orders.service import OrderService
from app.modules.users.service import UserService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        async with httpx.AsyncClient() as http_client:

            def uow_factory() -> UnitOfWork:
                return UnitOfWork(async_session_maker)

            restaurant_client = RestaurantClient(
                settings.DEMO_RESTAURANT_URL, http_client
            )
            email_client = EmailClient(
                host=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                sender=settings.SMTP_SENDER,
                timeout=settings.SMTP_TIMEOUT_SECONDS,
                use_tls=settings.SMTP_USE_TLS,
                start_tls=settings.SMTP_START_TLS,
                validate_certs=settings.SMTP_VALIDATE_CERTS,
                base_url=settings.EMAIL_VERIFICATION_BASE_URL,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
            )
            app.state.rate_limiter = InMemoryRateLimiter(
                max_buckets=settings.AUTH_RATE_LIMIT_MAX_BUCKETS,
                cleanup_interval_seconds=settings.AUTH_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS,
            )
            app.state.catalog_service = CatalogService(uow_factory)
            app.state.sync_service = SyncService(uow_factory)
            app.state.cart_service = CartService(uow_factory)
            app.state.order_service = OrderService(
                uow_factory, restaurant_client
            )
            app.state.checkout_service = CheckoutService(
                app.state.cart_service, app.state.order_service, uow_factory
            )
            app.state.registration_service = RegistrationService(
                email_client, uow_factory, UserService()
            )
            yield
    finally:
        await engine.dispose()
