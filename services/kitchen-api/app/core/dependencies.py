from fastapi import Request

from app.modules.auth.registration import RegistrationService
from app.modules.cart.service import CartService
from app.modules.catalog.service import CatalogService
from app.modules.catalog.sync.service import SyncService
from app.modules.checkout.service import CheckoutService
from app.modules.orders.service import OrderService


def get_catalog_service(request: Request) -> CatalogService:
    return request.app.state.catalog_service


def get_sync_service(request: Request) -> SyncService:
    return request.app.state.sync_service


def get_cart_service(request: Request) -> CartService:
    return request.app.state.cart_service


def get_checkout_service(request: Request) -> CheckoutService:
    return request.app.state.checkout_service


def get_order_service(request: Request) -> OrderService:
    return request.app.state.order_service


def get_registration_service(request: Request) -> RegistrationService:
    return request.app.state.registration_service
