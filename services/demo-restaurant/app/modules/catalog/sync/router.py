from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_catalog_sync_service
from app.modules.catalog.sync.schemas import SyncResponse
from app.modules.catalog.sync.service import CatalogSyncService

router = APIRouter()


@router.post("/sync")
async def sync(
    service: Annotated[CatalogSyncService, Depends(get_catalog_sync_service)],
) -> SyncResponse:
    return await service.sync()
