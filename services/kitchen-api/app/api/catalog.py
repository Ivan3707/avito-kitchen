from uuid import UUID

from fastapi import APIRouter, Depends

from app.infrastructure.database.session import async_session_maker
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.catalog import (
    BranchMenuResponse,
    BranchResponse,
    RestaurantResponse,
)
from app.services.catalog import CatalogService

router = APIRouter(
    prefix="/api/v1",
    tags=["catalog"],
)


def get_uow() -> UnitOfWork:
    return UnitOfWork(async_session_maker)


@router.get(
    "/restaurants",
    response_model=list[RestaurantResponse],
)
async def get_restaurants(
    uow: UnitOfWork = Depends(get_uow),
) -> list[RestaurantResponse]:
    service = CatalogService()

    async with uow:
        return await service.get_restaurants(uow)


@router.get(
    "/restaurants/{restaurant_id}/branches",
    response_model=list[BranchResponse],
)
async def get_branches(
    restaurant_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> list[BranchResponse]:
    service = CatalogService()

    async with uow:
        return await service.get_branches(
            uow=uow,
            restaurant_id=restaurant_id,
        )


@router.get(
    "/branches/{branch_id}/menu",
    response_model=BranchMenuResponse,
)
async def get_branch_menu(
    branch_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> BranchMenuResponse:
    service = CatalogService()

    async with uow:
        return await service.get_branch_menu(
            uow=uow,
            branch_id=branch_id,
        )
