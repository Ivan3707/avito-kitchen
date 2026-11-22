"""complete integration transition

Revision ID: 4d2a9f7c1b30
Revises: de185c05ef9f
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "4d2a9f7c1b30"
down_revision: Union[str, Sequence[str], None] = "de185c05ef9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column("last_snapshot_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "restaurants",
        sa.Column(
            "last_snapshot_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_restaurants_last_snapshot_id",
        "restaurants",
        ["last_snapshot_id"],
    )
    op.drop_constraint(
        "ck_restaurant_sync_version_non_negative",
        "restaurants",
        type_="check",
    )
    op.drop_column("restaurants", "sync_version")

    op.create_table(
        "sync_snapshots",
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("restaurant_id", sa.UUID(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "ix_sync_snapshots_restaurant_id",
        "sync_snapshots",
        ["restaurant_id"],
    )

    op.add_column(
        "orders",
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="confirmed",
            nullable=False,
        ),
    )
    op.add_column(
        "orders", sa.Column("rejection_code", sa.String(), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("rejection_message", sa.String(), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column(
            "rejection_menu_item_external_id", sa.String(), nullable=True
        ),
    )
    op.add_column(
        "orders", sa.Column("rejection_old_price", sa.Integer(), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column("rejection_current_price", sa.Integer(), nullable=True),
    )
    op.alter_column(
        "orders",
        "restaurant_order_id",
        existing_type=sa.String(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_order_status",
        "orders",
        "status IN ('pending', 'confirmed', 'rejected')",
    )
    op.create_check_constraint(
        "ck_order_result_consistency",
        "orders",
        "(status = 'confirmed' AND restaurant_order_id IS NOT NULL "
        "AND rejection_code IS NULL AND rejection_message IS NULL) OR "
        "(status = 'rejected' AND restaurant_order_id IS NULL "
        "AND rejection_code IS NOT NULL AND rejection_message IS NOT NULL) OR "
        "(status = 'pending' AND restaurant_order_id IS NULL "
        "AND rejection_code IS NULL AND rejection_message IS NULL)",
    )
    op.alter_column("orders", "status", server_default="pending")


def downgrade() -> None:
    op.drop_constraint("ck_order_result_consistency", "orders", type_="check")
    op.drop_constraint("ck_order_status", "orders", type_="check")
    pending_orders = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM orders WHERE restaurant_order_id IS NULL"
            )
        )
        .scalar_one()
    )
    if pending_orders:
        raise RuntimeError(
            "cannot downgrade while pending or rejected orders exist"
        )
    op.alter_column(
        "orders",
        "restaurant_order_id",
        existing_type=sa.String(),
        nullable=False,
    )
    for column in (
        "rejection_current_price",
        "rejection_old_price",
        "rejection_menu_item_external_id",
        "rejection_message",
        "rejection_code",
        "status",
    ):
        op.drop_column("orders", column)
    op.drop_index(
        "ix_sync_snapshots_restaurant_id", table_name="sync_snapshots"
    )
    op.drop_table("sync_snapshots")
    op.add_column(
        "restaurants",
        sa.Column(
            "sync_version", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_restaurant_sync_version_non_negative",
        "restaurants",
        "sync_version >= 0",
    )
    op.drop_constraint(
        "uq_restaurants_last_snapshot_id", "restaurants", type_="unique"
    )
    op.drop_column("restaurants", "last_snapshot_generated_at")
    op.drop_column("restaurants", "last_snapshot_id")
