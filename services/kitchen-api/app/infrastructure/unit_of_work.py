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
        self.session: AsyncSession | None = None
        self.session_factory = session_factory
        self._entered = False

    async def __aenter__(self):
        if self._entered:
            raise RuntimeError("UnitOfWork cannot be entered more than once")

        self._entered = True
        try:
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
        except BaseException as exc:
            if self.session is not None:
                try:
                    await self.session.close()
                except BaseException as close_exc:
                    exc.add_note(f"Additionally, session closing failed: {close_exc!r}")

            raise

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        error = exc_value

        try:
            if exc_type is not None:
                await self.rollback()
            else:
                await self.commit()
        except BaseException as transaction_exc:
            if error is not None:
                error.add_note(f"Additionally, transaction failed: {transaction_exc!r}")
            else:
                error = transaction_exc

        try:
            await self.session.close()
        except BaseException as close_exc:
            if error is not None:
                error.add_note(f"Additionally, session closing failed: {close_exc!r}")
            else:
                raise

        if exc_value is None and error is not None:
            raise error

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
