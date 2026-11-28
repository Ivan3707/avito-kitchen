from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.repositories.branch_menu_item import (
    BranchMenuItemRepository,
)
from app.modules.catalog.repositories.menu import MenuRepository
from app.modules.catalog.repositories.menu_item import MenuItemRepository
from app.modules.catalog.repositories.restaurant import RestaurantRepository
from app.modules.catalog.repositories.restaurant_branch import (
    RestaurantBranchRepository,
)
from app.modules.catalog.repositories.sync_snapshot import (
    SyncSnapshotRepository,
)


class CatalogRepositories:
    def __init__(self, session: AsyncSession):
        self.restaurants = RestaurantRepository(session)
        self.restaurant_branches = RestaurantBranchRepository(session)
        self.menus = MenuRepository(session)
        self.menu_items = MenuItemRepository(session)
        self.branch_menu_items = BranchMenuItemRepository(session)
        self.sync_snapshots = SyncSnapshotRepository(session)
