from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.repositories.branch_menu_item import (
    BranchMenuItemRepository,
)
from app.infrastructure.repositories.cart import CartRepository
from app.infrastructure.repositories.customer import CustomerRepository
from app.infrastructure.repositories.menu import MenuRepository
from app.infrastructure.repositories.menu_item import MenuItemRepository
from app.infrastructure.repositories.order import OrderRepository
from app.infrastructure.repositories.restaurant import RestaurantRepository
from app.infrastructure.repositories.restaurant_branch import (
    RestaurantBranchRepository,
)


class UnitOfWork:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.session_factory = session_factory

    async def __aenter__(self):
        self.session = self.session_factory()

        self.restaurants = RestaurantRepository(self.session)
        self.customers = CustomerRepository(self.session)
        self.restaurant_branches = RestaurantBranchRepository(self.session)
        self.menus = MenuRepository(self.session)
        self.menu_items = MenuItemRepository(self.session)
        self.orders = OrderRepository(self.session)
        self.carts = CartRepository(self.session)
        self.branch_menu_items = BranchMenuItemRepository(self.session)

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

        await self.session.close()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
