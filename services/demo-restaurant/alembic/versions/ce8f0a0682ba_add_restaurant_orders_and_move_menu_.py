"""add restaurant orders and move menu item price

Revision ID: ce8f0a0682ba
Revises: 7c6cc5520fdb
Create Date: 2026-11-05 16:10:04.142061

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce8f0a0682ba'
down_revision: Union[str, Sequence[str], None] = '7c6cc5520fdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "restaurant_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            """
            (
                accepted = TRUE
                AND status != 'rejected'
                AND rejection_reason IS NULL
            )
            OR
            (
                accepted = FALSE
                AND status = 'rejected'
                AND rejection_reason IS NOT NULL
            )
            """,
            name="ck_restaurant_order_result_consistency",
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'rejected', 'preparing', 'ready', 'completed', 'cancelled')",
            name="ck_restaurant_order_status",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["restaurant_branches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_id",
            name="uq_restaurant_order_external_id",
        ),
    )

    op.create_table(
        "restaurant_order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("menu_item_id", sa.UUID(), nullable=True),
        sa.Column("menu_item_external_id", sa.String(), nullable=False),
        sa.Column("menu_item_name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_restaurant_order_item_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price > 0",
            name="ck_restaurant_order_item_price_positive",
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["restaurant_orders.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_column("branch_menu_items", "price")

    op.add_column(
        "menu_items",
        sa.Column("price", sa.Integer(), nullable=False),
    )

    op.create_check_constraint(
        "ck_menu_item_price_positive",
        "menu_items",
        "price > 0",
    )


def downgrade() -> None:
    op.drop_table("restaurant_order_items")
    op.drop_table("restaurant_orders")

    # Возвращаем цену в филиальную таблицу.
    op.add_column(
        "branch_menu_items",
        sa.Column("price", sa.Integer(), nullable=True),
    )

    # Восстанавливаем цену из MenuItem.
    op.execute(
        """
        UPDATE branch_menu_items AS bmi
        SET price = mi.price
        FROM menu_items AS mi
        WHERE bmi.menu_item_id = mi.id
        """
    )

    op.alter_column(
        "branch_menu_items",
        "price",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.drop_constraint(
        "ck_menu_item_price_positive",
        "menu_items",
        type_="check",
    )
    op.drop_column("menu_items", "price")