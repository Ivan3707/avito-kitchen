from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.repositories.branch_menu_item import (
    BranchMenuItemRepository,
)
from app.modules.catalog.repositories.catalog_state import (
    CatalogStateRepository,
)
from app.modules.catalog.repositories.menu_item import MenuItemRepository
from app.modules.catalog.repositories.restaurant_branch import (
    RestaurantBranchRepository,
)


class CatalogRepositories:
    def __init__(self, session: AsyncSession):
        self.restaurant_branches = RestaurantBranchRepository(session)
        self.menu_items = MenuItemRepository(session)
        self.branch_menu_items = BranchMenuItemRepository(session)
        self.catalog_state = CatalogStateRepository(session)
