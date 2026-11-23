"""move menu item price to branch menu item

Revision ID: 8f3c1a7d2e40
Revises: 4d2a9f7c1b30
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8f3c1a7d2e40"
down_revision: Union[str, Sequence[str], None] = "4d2a9f7c1b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "branch_menu_items",
        sa.Column("price", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE branch_menu_items AS branch_item "
        "SET price = menu_item.price "
        "FROM menu_items AS menu_item "
        "WHERE branch_item.menu_item_id = menu_item.id"
    )
    op.create_check_constraint(
        "ck_branch_menu_item_price_positive",
        "branch_menu_items",
        "price IS NULL OR price > 0",
    )
    op.create_check_constraint(
        "ck_branch_menu_item_available_requires_price",
        "branch_menu_items",
        "NOT is_available OR (price IS NOT NULL AND price > 0)",
    )
    op.drop_constraint(
        "ck_menu_item_price_positive",
        "menu_items",
        type_="check",
    )
    op.drop_column("menu_items", "price")


def downgrade() -> None:
    op.execute(
        "LOCK TABLE menu_items, branch_menu_items "
        "IN ACCESS EXCLUSIVE MODE"
    )
    unsafe_items = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM menu_items AS menu_item "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM branch_menu_items AS branch_item "
                "  WHERE branch_item.menu_item_id = menu_item.id"
                ") OR EXISTS ("
                "  SELECT 1 FROM branch_menu_items AS branch_item "
                "  WHERE branch_item.menu_item_id = menu_item.id "
                "    AND branch_item.price IS NULL"
                ") OR ("
                "  SELECT count(DISTINCT branch_item.price) "
                "  FROM branch_menu_items AS branch_item "
                "  WHERE branch_item.menu_item_id = menu_item.id"
                ") <> 1"
            )
        )
        .scalar_one()
    )
    if unsafe_items:
        raise RuntimeError(
            "cannot downgrade branch pricing: every menu item must have "
            "one identical non-null price across all existing branch links"
        )

    op.add_column(
        "menu_items",
        sa.Column("price", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE menu_items AS menu_item "
        "SET price = branch_price.price "
        "FROM ("
        "  SELECT menu_item_id, min(price) AS price "
        "  FROM branch_menu_items GROUP BY menu_item_id"
        ") AS branch_price "
        "WHERE menu_item.id = branch_price.menu_item_id"
    )
    op.alter_column(
        "menu_items",
        "price",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_menu_item_price_positive",
        "menu_items",
        "price > 0",
    )
    op.drop_constraint(
        "ck_branch_menu_item_available_requires_price",
        "branch_menu_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_branch_menu_item_price_positive",
        "branch_menu_items",
        type_="check",
    )
    op.drop_column("branch_menu_items", "price")
