from dataclasses import dataclass, field
from functools import wraps
from types import TracebackType
from typing import Any

from app.infrastructure.database.models.branch_menu_item import BranchMenuItem
from app.infrastructure.database.models.catalog_state import CatalogState
from app.infrastructure.database.models.menu_item import MenuItem
from app.infrastructure.database.models.restaurant_branch import (
    RestaurantBranch,
)
from app.infrastructure.unit_of_work import UnitOfWork


class CatalogMutationError(Exception):
    pass


class CatalogNotFoundError(CatalogMutationError):
    pass


class CatalogConflictError(CatalogMutationError):
    pass


class CatalogInvariantError(CatalogMutationError):
    pass


class _UnsetType:
    pass


_UNSET = _UnsetType()


def _rollback_on_error(method: Any) -> Any:
    @wraps(method)
    async def wrapper(
        self: "CatalogMutationService",
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        try:
            return await method(self, *args, **kwargs)
        except BaseException:
            self.uow.mark_rollback_only()
            raise

    return wrapper


@dataclass(frozen=True)
class _CatalogBusinessState:
    metadata: tuple[str, str | None, str]
    branches: tuple[tuple[str, str, str, bool, bool], ...]
    menu_items: tuple[tuple[str, str, str | None, bool], ...]
    relations: tuple[tuple[str, str, int | None, bool], ...]
    branch_versions: tuple[tuple[str, int], ...] = field(compare=False)
    branch_entities: tuple[RestaurantBranch, ...] = field(
        compare=False,
        repr=False,
    )


class CatalogMutationService:
    """Mutate catalog state inside an existing UnitOfWork transaction."""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        self._catalog_state: CatalogState | None = None
        self._active = False

    async def __aenter__(self) -> "CatalogMutationService":
        if self._active or self.uow._catalog_mutation_active:
            raise RuntimeError("another catalog mutation is already active")
        if self.uow._rollback_only:
            raise RuntimeError("UnitOfWork transaction is rollback-only")
        try:
            self._catalog_state = (
                await self.uow.catalog_state.get_for_update()
            )
            if self.uow._catalog_initial_state is None:
                self.uow._catalog_initial_state = (
                    await self._capture_business_state(self._catalog_state)
                )
                self.uow._catalog_initial_revision = (
                    self._catalog_state.catalog_revision
                )
        except BaseException:
            self.uow.mark_rollback_only()
            raise
        self.uow.mark_catalog_transaction_started()
        self.uow._catalog_mutation_active = True
        self._active = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                self.uow.mark_rollback_only()
                return
            await self.uow.flush()
            current_state = await self._capture_business_state(
                self._require_active()
            )
            initial_state = self.uow._catalog_initial_state
            initial_revision = self.uow._catalog_initial_revision
            if not isinstance(initial_state, _CatalogBusinessState) or (
                initial_revision is None
            ):
                raise RuntimeError("initial catalog state is missing")
            self._reconcile_branch_versions(initial_state, current_state)
            self._require_active().catalog_revision = initial_revision + int(
                current_state != initial_state
            )
        except BaseException:
            self.uow.mark_rollback_only()
            raise
        finally:
            self.uow._catalog_mutation_active = False
            self._active = False

    @_rollback_on_error
    async def update_restaurant(
        self,
        *,
        name: str | _UnsetType = _UNSET,
        description: str | None | _UnsetType = _UNSET,
    ) -> bool:
        state = self._require_active()
        changed = False
        if not isinstance(name, _UnsetType):
            self._require_non_empty(name, "restaurant name")
            changed |= self._assign(state, "restaurant_name", name)
        if not isinstance(description, _UnsetType):
            changed |= self._assign(
                state, "restaurant_description", description
            )
        return changed

    @_rollback_on_error
    async def update_menu(
        self,
        *,
        name: str,
    ) -> bool:
        state = self._require_active()
        self._require_non_empty(name, "menu name")
        changed = self._assign(state, "menu_name", name)
        return changed

    @_rollback_on_error
    async def create_branch(
        self,
        *,
        external_id: str,
        name: str,
        address: str,
        is_active: bool = True,
        is_accepting_orders: bool = False,
    ) -> RestaurantBranch:
        self._require_active()
        self._require_non_empty(external_id, "branch external_id")
        self._require_non_empty(name, "branch name")
        self._require_non_empty(address, "branch address")
        self._validate_branch_state(is_active, is_accepting_orders)
        existing = await self.uow.restaurant_branches.get_by_external_id(
            external_id
        )
        if existing is not None:
            if (
                existing.name == name
                and existing.address == address
                and existing.is_active is is_active
                and existing.is_accepting_orders is is_accepting_orders
            ):
                return existing
            raise CatalogConflictError(
                f"branch {external_id!r} already exists with other values"
            )
        branch = self.uow.restaurant_branches.add(
            RestaurantBranch(
                external_id=external_id,
                name=name,
                address=address,
                is_active=is_active,
                is_accepting_orders=is_accepting_orders,
                branch_version=1,
            )
        )
        return branch

    @_rollback_on_error
    async def update_branch(
        self,
        external_id: str,
        *,
        name: str | _UnsetType = _UNSET,
        address: str | _UnsetType = _UNSET,
        is_active: bool | _UnsetType = _UNSET,
        is_accepting_orders: bool | _UnsetType = _UNSET,
    ) -> bool:
        self._require_active()
        branch = await self._get_branch(external_id)
        next_active = (
            branch.is_active
            if isinstance(is_active, _UnsetType)
            else is_active
        )
        next_accepting = (
            branch.is_accepting_orders
            if isinstance(is_accepting_orders, _UnsetType)
            else is_accepting_orders
        )
        if next_active is False and isinstance(
            is_accepting_orders, _UnsetType
        ):
            next_accepting = False
        self._validate_branch_state(next_active, next_accepting)

        changed = False
        if not isinstance(name, _UnsetType):
            self._require_non_empty(name, "branch name")
            changed |= self._assign(branch, "name", name)
        if not isinstance(address, _UnsetType):
            self._require_non_empty(address, "branch address")
            changed |= self._assign(branch, "address", address)
        changed |= self._assign(branch, "is_active", next_active)
        changed |= self._assign(
            branch, "is_accepting_orders", next_accepting
        )
        return changed

    @_rollback_on_error
    async def deactivate_branch(self, external_id: str) -> bool:
        return await self.update_branch(
            external_id,
            is_active=False,
            is_accepting_orders=False,
        )

    @_rollback_on_error
    async def create_menu_item(
        self,
        *,
        external_id: str,
        name: str,
        description: str | None = None,
        is_active: bool = True,
    ) -> MenuItem:
        self._require_active()
        self._require_non_empty(external_id, "menu item external_id")
        self._require_non_empty(name, "menu item name")
        self._require_bool(is_active, "menu item is_active")
        existing = await self.uow.menu_items.get_by_external_id(external_id)
        if existing is not None:
            if (
                existing.name == name
                and existing.description == description
                and existing.is_active is is_active
            ):
                return existing
            raise CatalogConflictError(
                f"menu item {external_id!r} already exists with other values"
            )
        menu_item = self.uow.menu_items.add(
            MenuItem(
                external_id=external_id,
                name=name,
                description=description,
                is_active=is_active,
            )
        )
        return menu_item

    @_rollback_on_error
    async def update_menu_item(
        self,
        external_id: str,
        *,
        name: str | _UnsetType = _UNSET,
        description: str | None | _UnsetType = _UNSET,
        is_active: bool | _UnsetType = _UNSET,
    ) -> bool:
        self._require_active()
        menu_item = await self._get_menu_item(external_id)
        changed = False
        if not isinstance(name, _UnsetType):
            self._require_non_empty(name, "menu item name")
            changed |= self._assign(menu_item, "name", name)
        if not isinstance(description, _UnsetType):
            changed |= self._assign(menu_item, "description", description)
        if not isinstance(is_active, _UnsetType):
            self._require_bool(is_active, "menu item is_active")
            changed |= self._assign(menu_item, "is_active", is_active)
        return changed

    @_rollback_on_error
    async def deactivate_menu_item(self, external_id: str) -> bool:
        return await self.update_menu_item(external_id, is_active=False)

    @_rollback_on_error
    async def create_branch_menu_item(
        self,
        *,
        branch_external_id: str,
        menu_item_external_id: str,
        price: int | None = None,
        is_available: bool = False,
    ) -> BranchMenuItem:
        self._require_active()
        branch = await self._get_branch(branch_external_id)
        menu_item = await self._get_menu_item(menu_item_external_id)
        self._validate_branch_menu_item(
            branch, menu_item, price, is_available
        )
        existing = (
            await self.uow.branch_menu_items.get_by_branch_and_menu_item(
                branch.id, menu_item.id
            )
        )
        if existing is not None:
            if (
                existing.price == price
                and existing.is_available is is_available
            ):
                return existing
            raise CatalogConflictError(
                "branch menu item already exists with other values"
            )
        relation = self.uow.branch_menu_items.add(
            BranchMenuItem(
                branch_id=branch.id,
                menu_item_id=menu_item.id,
                price=price,
                is_available=is_available,
            )
        )
        return relation

    @_rollback_on_error
    async def update_branch_menu_item(
        self,
        *,
        branch_external_id: str,
        menu_item_external_id: str,
        price: int | None | _UnsetType = _UNSET,
        is_available: bool | _UnsetType = _UNSET,
    ) -> bool:
        self._require_active()
        branch = await self._get_branch(branch_external_id)
        menu_item = await self._get_menu_item(menu_item_external_id)
        relation = (
            await self.uow.branch_menu_items.get_by_branch_and_menu_item(
                branch.id, menu_item.id
            )
        )
        if relation is None:
            raise CatalogNotFoundError("branch menu item not found")
        next_price = (
            relation.price if isinstance(price, _UnsetType) else price
        )
        next_available = (
            relation.is_available
            if isinstance(is_available, _UnsetType)
            else is_available
        )
        self._validate_branch_menu_item(
            branch, menu_item, next_price, next_available
        )
        changed = self._assign(relation, "price", next_price)
        changed |= self._assign(
            relation, "is_available", next_available
        )
        return changed

    @_rollback_on_error
    async def exclude_branch_menu_item(
        self,
        *,
        branch_external_id: str,
        menu_item_external_id: str,
    ) -> bool:
        return await self.update_branch_menu_item(
            branch_external_id=branch_external_id,
            menu_item_external_id=menu_item_external_id,
            is_available=False,
        )

    def _require_active(self) -> CatalogState:
        if not self._active or self._catalog_state is None:
            raise RuntimeError(
                "CatalogMutationService must be used as an async context manager"
            )
        return self._catalog_state

    async def _get_branch(self, external_id: str) -> RestaurantBranch:
        branch = await self.uow.restaurant_branches.get_by_external_id(
            external_id
        )
        if branch is None:
            raise CatalogNotFoundError(f"branch {external_id!r} not found")
        return branch

    async def _get_menu_item(self, external_id: str) -> MenuItem:
        menu_item = await self.uow.menu_items.get_by_external_id(external_id)
        if menu_item is None:
            raise CatalogNotFoundError(
                f"menu item {external_id!r} not found"
            )
        return menu_item

    async def _capture_business_state(
        self,
        catalog_state: CatalogState,
    ) -> _CatalogBusinessState:
        branches = await self.uow.restaurant_branches.get_all()
        menu_items = await self.uow.menu_items.get_all()
        relations = await self.uow.branch_menu_items.get_all()
        branch_ids = {
            branch.id: branch.external_id for branch in branches
        }
        menu_item_ids = {
            menu_item.id: menu_item.external_id for menu_item in menu_items
        }
        return _CatalogBusinessState(
            metadata=(
                catalog_state.restaurant_name,
                catalog_state.restaurant_description,
                catalog_state.menu_name,
            ),
            branches=tuple(
                sorted(
                    (
                        branch.external_id,
                        branch.name,
                        branch.address,
                        branch.is_active,
                        branch.is_accepting_orders,
                    )
                    for branch in branches
                )
            ),
            menu_items=tuple(
                sorted(
                    (
                        menu_item.external_id,
                        menu_item.name,
                        menu_item.description,
                        menu_item.is_active,
                    )
                    for menu_item in menu_items
                )
            ),
            relations=tuple(
                sorted(
                    (
                        branch_ids[relation.branch_id],
                        menu_item_ids[relation.menu_item_id],
                        relation.price,
                        relation.is_available,
                    )
                    for relation in relations
                )
            ),
            branch_versions=tuple(
                sorted(
                    (branch.external_id, branch.branch_version)
                    for branch in branches
                )
            ),
            branch_entities=tuple(branches),
        )

    def _reconcile_branch_versions(
        self,
        initial: _CatalogBusinessState,
        current: _CatalogBusinessState,
    ) -> None:
        initial_versions = dict(initial.branch_versions)
        for branch in current.branch_entities:
            external_id = branch.external_id
            initial_version = initial_versions.get(external_id)
            if initial_version is None:
                branch.branch_version = 1
                continue
            branch.branch_version = initial_version + int(
                self._branch_state(initial, external_id)
                != self._branch_state(current, external_id)
            )

    @staticmethod
    def _branch_state(
        state: _CatalogBusinessState,
        external_id: str,
    ) -> tuple[
        tuple[str, str, str, bool, bool] | None,
        tuple[tuple[str, str, int | None, bool], ...],
    ]:
        branch = next(
            (
                candidate
                for candidate in state.branches
                if candidate[0] == external_id
            ),
            None,
        )
        relations = tuple(
            relation
            for relation in state.relations
            if relation[0] == external_id
        )
        return branch, relations

    @staticmethod
    def _assign(entity: Any, attribute: str, value: Any) -> bool:
        if getattr(entity, attribute) == value:
            return False
        setattr(entity, attribute, value)
        return True

    @staticmethod
    def _require_non_empty(value: str, field: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise CatalogInvariantError(f"{field} must not be empty")

    @staticmethod
    def _require_bool(value: bool, field: str) -> None:
        if not isinstance(value, bool):
            raise CatalogInvariantError(f"{field} must be boolean")

    @staticmethod
    def _validate_branch_state(
        is_active: bool,
        is_accepting_orders: bool,
    ) -> None:
        CatalogMutationService._require_bool(is_active, "branch is_active")
        CatalogMutationService._require_bool(
            is_accepting_orders, "branch is_accepting_orders"
        )
        if not is_active and is_accepting_orders:
            raise CatalogInvariantError(
                "inactive branch cannot accept orders"
            )

    @staticmethod
    def _validate_branch_menu_item(
        branch: RestaurantBranch,
        menu_item: MenuItem,
        price: int | None,
        is_available: bool,
    ) -> None:
        CatalogMutationService._require_bool(
            is_available, "branch menu item is_available"
        )
        if price is not None and (
            isinstance(price, bool)
            or not isinstance(price, int)
            or price <= 0
        ):
            raise CatalogInvariantError(
                "price must be a positive integer or null"
            )
        if is_available and price is None:
            raise CatalogInvariantError(
                "available menu item requires a positive price"
            )
        if is_available and (not branch.is_active or not menu_item.is_active):
            raise CatalogInvariantError(
                "inactive branch or menu item cannot be available"
            )
