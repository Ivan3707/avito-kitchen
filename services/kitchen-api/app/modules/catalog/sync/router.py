from fastapi import APIRouter, Depends

from app.core.dependencies import get_sync_service
from app.modules.catalog.sync.schemas import SyncPayload, SyncResponse
from app.modules.catalog.sync.service import SyncService

router = APIRouter(prefix="/integration/v1", tags=["integration"])


@router.post("/sync", response_model=SyncResponse)
async def sync(
    payload: SyncPayload, service: SyncService = Depends(get_sync_service)
) -> SyncResponse:
    return await service.apply(payload)
