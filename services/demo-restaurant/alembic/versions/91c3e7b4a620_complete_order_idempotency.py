"""complete order idempotency

Revision ID: 91c3e7b4a620
Revises: 77a0f844904e
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "91c3e7b4a620"
down_revision: Union[str, Sequence[str], None] = "77a0f844904e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurant_orders",
        sa.Column("branch_external_id", sa.String(), nullable=True),
    )
    op.execute(
        "UPDATE restaurant_orders AS orders "
        "SET branch_external_id = branches.external_id "
        "FROM restaurant_branches AS branches "
        "WHERE orders.branch_id = branches.id"
    )
    op.alter_column("restaurant_orders", "branch_external_id", nullable=False)
    op.alter_column(
        "restaurant_orders",
        "branch_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.add_column(
        "restaurant_orders",
        sa.Column("rejection_code", sa.String(), nullable=True),
    )
    op.add_column(
        "restaurant_orders",
        sa.Column(
            "rejection_menu_item_external_id", sa.String(), nullable=True
        ),
    )
    op.add_column(
        "restaurant_orders",
        sa.Column("rejection_old_price", sa.Integer(), nullable=True),
    )
    op.add_column(
        "restaurant_orders",
        sa.Column("rejection_current_price", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE restaurant_orders SET rejection_code = 'RESTAURANT_REJECTED' "
        "WHERE accepted = FALSE"
    )
    op.drop_constraint(
        "ck_restaurant_order_result_consistency",
        "restaurant_orders",
        type_="check",
    )
    op.create_check_constraint(
        "ck_restaurant_order_result_consistency",
        "restaurant_orders",
        "(accepted = TRUE AND status != 'rejected' "
        "AND rejection_reason IS NULL AND rejection_code IS NULL) OR "
        "(accepted = FALSE AND status = 'rejected' "
        "AND rejection_reason IS NOT NULL AND rejection_code IS NOT NULL)",
    )


def downgrade() -> None:
    orders_without_branch = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM restaurant_orders "
                "WHERE branch_id IS NULL"
            )
        )
        .scalar_one()
    )
    if orders_without_branch:
        raise RuntimeError(
            "cannot downgrade while orders for unknown branches exist"
        )
    op.drop_constraint(
        "ck_restaurant_order_result_consistency",
        "restaurant_orders",
        type_="check",
    )
    op.create_check_constraint(
        "ck_restaurant_order_result_consistency",
        "restaurant_orders",
        "(accepted = TRUE AND status != 'rejected' "
        "AND rejection_reason IS NULL) OR "
        "(accepted = FALSE AND status = 'rejected' "
        "AND rejection_reason IS NOT NULL)",
    )
    for column in (
        "rejection_current_price",
        "rejection_old_price",
        "rejection_menu_item_external_id",
        "rejection_code",
    ):
        op.drop_column("restaurant_orders", column)
    op.alter_column(
        "restaurant_orders",
        "branch_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("restaurant_orders", "branch_external_id")
