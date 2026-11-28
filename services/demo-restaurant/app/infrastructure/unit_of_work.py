from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.catalog.repositories.group import CatalogRepositories
from app.modules.orders.repositories.group import OrderRepositories


class UnitOfWork:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        isolation_level: str | None = None,
    ):
        self.session: AsyncSession | None = None
        self.session_factory = session_factory
        self.isolation_level = isolation_level
        self._entered = False
        self._catalog_mutation_active = False
        self._catalog_initial_state: object | None = None
        self._catalog_initial_revision: int | None = None
        self._catalog_transaction_started = False
        self._rollback_only = False

    async def __aenter__(self):
        if self._entered:
            raise RuntimeError("UnitOfWork cannot be entered more than once")

        self._entered = True

        try:
            self.session = self.session_factory()

            if self.isolation_level is not None:
                await self.session.connection(
                    execution_options={
                        "isolation_level": self.isolation_level,
                    }
                )

            self.catalog = CatalogRepositories(self.session)
            self.orders = OrderRepositories(self.session)

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
            if exc_type is not None or self._rollback_only:
                await self._rollback_on_exit()
                if exc_type is None:
                    error = RuntimeError(
                        "UnitOfWork transaction is marked rollback-only"
                    )
            else:
                await self._commit_on_exit()
        except BaseException as transaction_exc:
            try:
                await self._rollback_on_exit()
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
        if self._catalog_transaction_started:
            self.mark_rollback_only()
            raise RuntimeError(
                "manual commit is not allowed after a catalog mutation "
                "transaction has started"
            )
        if self._rollback_only:
            await self.session.rollback()
            raise RuntimeError(
                "UnitOfWork transaction is marked rollback-only"
            )
        await self.session.commit()

    async def rollback(self):
        if self._catalog_transaction_started:
            self.mark_rollback_only()
            raise RuntimeError(
                "manual rollback is not allowed after a catalog mutation "
                "transaction has started"
            )
        await self.session.rollback()

    async def flush(self):
        await self.session.flush()

    def mark_rollback_only(self) -> None:
        self._rollback_only = True

    def mark_catalog_transaction_started(self) -> None:
        self._catalog_transaction_started = True

    async def _commit_on_exit(self) -> None:
        await self.session.commit()

    async def _rollback_on_exit(self) -> None:
        await self.session.rollback()
