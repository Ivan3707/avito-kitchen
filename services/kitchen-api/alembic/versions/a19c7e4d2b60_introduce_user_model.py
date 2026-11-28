"""introduce user model

Revision ID: a19c7e4d2b60
Revises: c6e4a8f2d190

The upgrade intentionally removes existing customer, cart, and order test
data. A downgrade restores the previous schema shape but cannot restore those
deleted rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a19c7e4d2b60"
down_revision: Union[str, Sequence[str], None] = "c6e4a8f2d190"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM cart_items"))
    op.execute(sa.text("DELETE FROM order_items"))
    op.execute(sa.text("DELETE FROM carts"))
    op.execute(sa.text("DELETE FROM orders"))
    op.execute(sa.text("DELETE FROM customers"))

    op.rename_table("customers", "users")
    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT customers_pkey TO users_pkey"
    )
    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT customers_email_key "
        "TO users_email_key"
    )

    op.alter_column("carts", "customer_id", new_column_name="user_id")
    op.execute(
        "ALTER TABLE carts RENAME CONSTRAINT carts_customer_id_fkey "
        "TO carts_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE carts RENAME CONSTRAINT uq_cart_customer_branch "
        "TO uq_cart_user_branch"
    )

    op.alter_column("orders", "customer_id", new_column_name="user_id")
    op.execute(
        "ALTER TABLE orders RENAME CONSTRAINT orders_customer_id_fkey "
        "TO orders_user_id_fkey"
    )

    op.add_column(
        "users",
        sa.Column("password_hash", sa.Text(), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(),
            server_default="customer",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_user_role",
        "users",
        "role IN ('customer', 'admin')",
    )


def downgrade() -> None:
    # The rows explicitly deleted during upgrade cannot be reconstructed.
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.drop_column("users", "is_active")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")

    op.execute(
        "ALTER TABLE orders RENAME CONSTRAINT orders_user_id_fkey "
        "TO orders_customer_id_fkey"
    )
    op.alter_column("orders", "user_id", new_column_name="customer_id")

    op.execute(
        "ALTER TABLE carts RENAME CONSTRAINT uq_cart_user_branch "
        "TO uq_cart_customer_branch"
    )
    op.execute(
        "ALTER TABLE carts RENAME CONSTRAINT carts_user_id_fkey "
        "TO carts_customer_id_fkey"
    )
    op.alter_column("carts", "user_id", new_column_name="customer_id")

    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT users_email_key "
        "TO customers_email_key"
    )
    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT users_pkey TO customers_pkey"
    )
    op.rename_table("users", "customers")
