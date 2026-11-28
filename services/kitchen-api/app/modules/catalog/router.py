from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import get_catalog_service
from app.modules.catalog.schemas import (
    BranchMenuResponse,
    BranchResponse,
    RestaurantResponse,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(
    prefix="/api/v1",
    tags=["catalog"],
)


@router.get(
    "/restaurants",
    response_model=list[RestaurantResponse],
)
async def get_restaurants(
    service: CatalogService = Depends(get_catalog_service),
) -> list[RestaurantResponse]:
    return await service.list_restaurants()


@router.get(
    "/restaurants/{restaurant_id}/branches",
    response_model=list[BranchResponse],
)
async def get_branches(
    restaurant_id: UUID,
    service: CatalogService = Depends(get_catalog_service),
) -> list[BranchResponse]:
    return await service.list_branches(restaurant_id)


@router.get(
    "/branches/{branch_id}/menu",
    response_model=BranchMenuResponse,
)
async def get_branch_menu(
    branch_id: UUID,
    service: CatalogService = Depends(get_catalog_service),
) -> BranchMenuResponse:
    return await service.get_menu(branch_id)
