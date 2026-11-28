from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth.repositories.group import AuthRepositories
from app.modules.cart.repositories.group import CartRepositories
from app.modules.catalog.repositories.group import CatalogRepositories
from app.modules.orders.repositories.group import OrderRepositories
from app.modules.users.repositories.group import UserRepositories


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

            self.catalog = CatalogRepositories(self.session)
            self.cart = CartRepositories(self.session)
            self.orders = OrderRepositories(self.session)
            self.users = UserRepositories(self.session)
            self.auth = AuthRepositories(self.session)
            return self
        except BaseException as exc:
            if self.session is not None:
                try:
                    await self.session.close()
                except BaseException as close_exc:
                    exc.add_note(
                        f"Additionally, session closing failed: {close_exc!r}"
                    )

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
            try:
                await self.rollback()
            except BaseException as rollback_exc:
                transaction_exc.add_note(
                    f"Additionally, rollback failed: {rollback_exc!r}"
                )
            if error is not None:
                error.add_note(
                    f"Additionally, transaction failed: {transaction_exc!r}"
                )
            else:
                error = transaction_exc

        try:
            await self.session.close()
        except BaseException as close_exc:
            if error is not None:
                error.add_note(
                    f"Additionally, session closing failed: {close_exc!r}"
                )
            else:
                raise

        if exc_value is None and error is not None:
            raise error

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()

    async def flush(self):
        await self.session.flush()


UowFactory = Callable[[], UnitOfWork]
