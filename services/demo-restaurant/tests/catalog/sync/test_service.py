from uuid import uuid4

import pytest

from app.modules.catalog.models.branch_menu_item import BranchMenuItem
from app.modules.catalog.models.menu_item import MenuItem
from app.modules.catalog.models.restaurant_branch import RestaurantBranch
from app.modules.catalog.sync.service import CatalogSyncService

pytestmark = pytest.mark.unit


def test_snapshot_contains_branch_specific_prices() -> None:
    first_branch = RestaurantBranch(
        id=uuid4(),
        external_id="branch-1",
        name="First",
        address="Address 1",
        is_active=True,
        is_accepting_orders=True,
        branch_version=1,
    )
    second_branch = RestaurantBranch(
        id=uuid4(),
        external_id="branch-2",
        name="Second",
        address="Address 2",
        is_active=True,
        is_accepting_orders=True,
        branch_version=1,
    )
    item = MenuItem(
        id=uuid4(),
        external_id="item-1",
        name="Item",
        description=None,
        is_active=True,
    )
    relations = [
        BranchMenuItem(
            branch_id=first_branch.id,
            menu_item_id=item.id,
            is_available=True,
            price=100,
        ),
        BranchMenuItem(
            branch_id=second_branch.id,
            menu_item_id=item.id,
            is_available=True,
            price=175,
        ),
    ]

    availability = CatalogSyncService._build_availability(
        [first_branch, second_branch], [item], relations
    )

    assert availability[0].items[0].price == 100
    assert availability[1].items[0].price == 175


def test_snapshot_marks_missing_branch_item_relation_unavailable() -> None:
    branch = RestaurantBranch(
        id=uuid4(),
        external_id="branch-1",
        name="Branch",
        address="Address",
        is_active=True,
        is_accepting_orders=True,
        branch_version=1,
    )
    item = MenuItem(
        id=uuid4(),
        external_id="item-1",
        name="Item",
        description=None,
        is_active=True,
    )

    availability = CatalogSyncService._build_availability([branch], [item], [])

    assert availability[0].items[0].price is None
    assert availability[0].items[0].is_available is False
