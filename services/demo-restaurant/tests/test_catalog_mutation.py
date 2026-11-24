import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.unit_of_work import UnitOfWork
from app.service.catalog_mutation import (
    CatalogConflictError,
    CatalogInvariantError,
    CatalogMutationService,
)
from app.service.service import DemoRestaurantService


async def revision(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with UnitOfWork(session_factory) as uow:
        return (await uow.catalog_state.get_current()).catalog_revision


async def create_catalog(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with UnitOfWork(session_factory) as uow:
        async with CatalogMutationService(uow) as catalog:
            await catalog.create_branch(
                external_id="branch-1",
                name="Branch",
                address="Address",
                is_active=True,
                is_accepting_orders=True,
            )
            await catalog.create_menu_item(
                external_id="item-1",
                name="Item",
            )
            await catalog.create_branch_menu_item(
                branch_external_id="branch-1",
                menu_item_external_id="item-1",
                price=100,
                is_available=True,
            )


@pytest.mark.asyncio
async def test_create_catalog_and_metadata_increment_once(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    async with UnitOfWork(factory) as uow:
        async with CatalogMutationService(uow) as catalog:
            await catalog.update_restaurant(
                name="Updated Restaurant",
                description="Description",
            )
            await catalog.update_menu(name="Updated Menu")
            await catalog.create_branch(
                external_id="branch-1",
                name="Branch",
                address="Address",
                is_active=True,
                is_accepting_orders=True,
            )
            await catalog.create_menu_item(
                external_id="item-1",
                name="Item",
                description="Description",
            )
            await catalog.create_branch_menu_item(
                branch_external_id="branch-1",
                menu_item_external_id="item-1",
                price=100,
                is_available=True,
            )
    assert await revision(factory) == 1
    async with UnitOfWork(factory) as uow:
        branch = await uow.restaurant_branches.get_by_external_id("branch-1")
        assert branch.branch_version == 1


@pytest.mark.asyncio
async def test_identical_operations_are_noop(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    await create_catalog(factory)
    async with UnitOfWork(factory) as uow:
        async with CatalogMutationService(uow) as catalog:
            await catalog.create_branch(
                external_id="branch-1",
                name="Branch",
                address="Address",
                is_active=True,
                is_accepting_orders=True,
            )
            await catalog.create_menu_item(
                external_id="item-1",
                name="Item",
            )
            await catalog.create_branch_menu_item(
                branch_external_id="branch-1",
                menu_item_external_id="item-1",
                price=100,
                is_available=True,
            )
            assert await catalog.update_branch(
                "branch-1", name="Branch"
            ) is False
            assert await catalog.update_menu_item(
                "item-1", name="Item"
            ) is False
            assert await catalog.update_branch_menu_item(
                branch_external_id="branch-1",
                menu_item_external_id="item-1",
                price=100,
                is_available=True,
            ) is False
    assert await revision(factory) == 1


@pytest.mark.asyncio
async def test_multiple_changes_increment_revision_and_branch_once(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    await create_catalog(factory)
    async with UnitOfWork(factory) as uow:
        async with CatalogMutationService(uow) as catalog:
            await catalog.update_restaurant(name="Other Restaurant")
            await catalog.update_menu(name="Other Menu")
            await catalog.update_branch("branch-1", name="Other Branch")
            await catalog.update_menu_item("item-1", name="Other Item")
            await catalog.update_branch_menu_item(
                branch_external_id="branch-1",
                menu_item_external_id="item-1",
                price=200,
                is_available=True,
            )
    assert await revision(factory) == 2
    async with UnitOfWork(factory) as uow:
        branch = await uow.restaurant_branches.get_by_external_id("branch-1")
        assert branch.branch_version == 2


@pytest.mark.asyncio
async def test_a_to_b_to_a_across_mutation_contexts_is_noop(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    await create_catalog(factory)
    async with UnitOfWork(factory) as uow:
        async with CatalogMutationService(uow) as catalog:
            await catalog.update_branch("branch-1", name="Temporary")
            await catalog.update_branch_menu_item(
                branch_external_id="branch-1",
                menu_item_external_id="item-1",
                price=200,
            )
        async with CatalogMutationService(uow) as catalog:
            await catalog.update_branch("branch-1", name="Branch")
            await catalog.update_branch_menu_item(
                branch_external_id="branch-1",
                menu_item_external_id="item-1",
                price=100,
            )
    assert await revision(factory) == 1
    async with UnitOfWork(factory) as uow:
        branch = await uow.restaurant_branches.get_by_external_id("branch-1")
        assert branch.branch_version == 1


@pytest.mark.asyncio
async def test_soft_delete_and_reactivation_are_versioned(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    await create_catalog(factory)
    async with UnitOfWork(factory) as uow:
        async with CatalogMutationService(uow) as catalog:
            await catalog.deactivate_branch("branch-1")
            await catalog.deactivate_menu_item("item-1")
    assert await revision(factory) == 2
    async with UnitOfWork(factory) as uow:
        async with CatalogMutationService(uow) as catalog:
            await catalog.update_branch(
                "branch-1",
                is_active=True,
                is_accepting_orders=True,
            )
            await catalog.update_menu_item("item-1", is_active=True)
    assert await revision(factory) == 3
    async with UnitOfWork(factory) as uow:
        branch = await uow.restaurant_branches.get_by_external_id("branch-1")
        assert branch.branch_version == 3


@pytest.mark.asyncio
async def test_rollback_discards_catalog_and_revision(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    with pytest.raises(RuntimeError, match="rollback requested"):
        async with UnitOfWork(factory) as uow:
            async with CatalogMutationService(uow) as catalog:
                await catalog.create_branch(
                    external_id="branch-1",
                    name="Branch",
                    address="Address",
                )
                raise RuntimeError("rollback requested")
    assert await revision(factory) == 0
    async with UnitOfWork(factory) as uow:
        assert (
            await uow.restaurant_branches.get_by_external_id("branch-1")
            is None
        )


@pytest.mark.asyncio
async def test_caught_mutation_error_makes_uow_rollback_only(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    with pytest.raises(RuntimeError, match="rollback-only"):
        async with UnitOfWork(factory) as uow:
            async with CatalogMutationService(uow) as catalog:
                await catalog.create_branch(
                    external_id="branch-1",
                    name="Branch",
                    address="Address",
                )
                with pytest.raises(CatalogInvariantError):
                    await catalog.create_menu_item(
                        external_id="item-1",
                        name="",
                    )
    assert await revision(factory) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["commit", "rollback"])
async def test_manual_transaction_end_is_forbidden_after_mutation_start(
    clean_catalog_database,
    operation: str,
) -> None:
    factory = clean_catalog_database
    with pytest.raises(RuntimeError, match="rollback-only"):
        async with UnitOfWork(factory) as uow:
            async with CatalogMutationService(uow) as catalog:
                await catalog.create_branch(
                    external_id="branch-1",
                    name="Branch",
                    address="Address",
                )
            with pytest.raises(RuntimeError, match=f"manual {operation}"):
                await getattr(uow, operation)()
    assert await revision(factory) == 0


@pytest.mark.asyncio
async def test_conflicting_duplicate_is_rejected_and_rolled_back(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    await create_catalog(factory)
    with pytest.raises(CatalogConflictError):
        async with UnitOfWork(factory) as uow:
            async with CatalogMutationService(uow) as catalog:
                await catalog.create_branch(
                    external_id="branch-1",
                    name="Conflicting",
                    address="Address",
                )
    assert await revision(factory) == 1


@pytest.mark.asyncio
async def test_concurrent_mutations_do_not_lose_revisions(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    await create_catalog(factory)
    first_has_lock = asyncio.Event()
    release_first = asyncio.Event()

    async def first_update() -> None:
        async with UnitOfWork(factory) as uow:
            async with CatalogMutationService(uow) as catalog:
                await catalog.update_branch_menu_item(
                    branch_external_id="branch-1",
                    menu_item_external_id="item-1",
                    price=200,
                )
                first_has_lock.set()
                await release_first.wait()

    async def second_update() -> None:
        await first_has_lock.wait()
        async with UnitOfWork(factory) as uow:
            async with CatalogMutationService(uow) as catalog:
                await catalog.update_branch_menu_item(
                    branch_external_id="branch-1",
                    menu_item_external_id="item-1",
                    price=300,
                )

    first_task = asyncio.create_task(first_update())
    await asyncio.wait_for(first_has_lock.wait(), timeout=2)
    second_task = asyncio.create_task(second_update())
    try:
        await asyncio.sleep(0.1)
        assert second_task.done() is False
    finally:
        release_first.set()
    await first_task
    await second_task

    assert await revision(factory) == 3
    async with UnitOfWork(factory) as uow:
        branch = await uow.restaurant_branches.get_by_external_id("branch-1")
        item = await uow.menu_items.get_by_external_id("item-1")
        relation = await uow.branch_menu_items.get_by_branch_and_menu_item(
            branch.id,
            item.id,
        )
        assert relation.price == 300
        assert branch.branch_version == 3


@pytest.mark.asyncio
async def test_snapshot_uses_current_revision_and_catalog_state(
    clean_catalog_database,
) -> None:
    factory = clean_catalog_database
    await create_catalog(factory)
    payload = await DemoRestaurantService(factory, object()).build_sync_payload()
    assert payload.schema_version == 3
    assert payload.catalog_revision == 1
    assert payload.branches[0].external_id == "branch-1"
    assert payload.availability[0].items[0].price == 100
    assert payload.availability[0].items[0].is_available is True
    assert not hasattr(payload.branches[0], "branch_version")
