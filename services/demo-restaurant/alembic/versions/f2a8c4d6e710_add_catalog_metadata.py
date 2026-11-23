"""add persistent catalog metadata

Revision ID: f2a8c4d6e710
Revises: d3f7a9c2e510
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

from app.core.config import settings

revision: str = "f2a8c4d6e710"
down_revision: Union[str, Sequence[str], None] = "d3f7a9c2e510"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "catalog_state",
        sa.Column("restaurant_name", sa.String(), nullable=True),
    )
    op.add_column(
        "catalog_state",
        sa.Column("restaurant_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "catalog_state",
        sa.Column("menu_name", sa.String(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE catalog_state "
            "SET restaurant_name = :restaurant_name, "
            "restaurant_description = :restaurant_description, "
            "menu_name = :menu_name "
            "WHERE id = 1"
        ).bindparams(
            restaurant_name=settings.restaurant_name,
            restaurant_description=settings.restaurant_description,
            menu_name=settings.menu_name,
        )
    )
    op.alter_column(
        "catalog_state",
        "restaurant_name",
        existing_type=sa.String(),
        nullable=False,
    )
    op.alter_column(
        "catalog_state",
        "menu_name",
        existing_type=sa.String(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("catalog_state", "menu_name")
    op.drop_column("catalog_state", "restaurant_description")
    op.drop_column("catalog_state", "restaurant_name")
