from fastapi import Request

from app.modules.catalog.sync.service import CatalogSyncService
from app.modules.orders.service import OrderService


def get_catalog_sync_service(request: Request) -> CatalogSyncService:
    return request.app.state.catalog_sync_service


def get_order_service(request: Request) -> OrderService:
    return request.app.state.order_service
