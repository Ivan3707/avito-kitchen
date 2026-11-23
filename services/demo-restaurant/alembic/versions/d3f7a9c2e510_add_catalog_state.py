"""add catalog revision state

Revision ID: d3f7a9c2e510
Revises: b4e6d8f1a230
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d3f7a9c2e510"
down_revision: Union[str, Sequence[str], None] = "b4e6d8f1a230"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    catalog_state = op.create_table(
        "catalog_state",
        sa.Column(
            "id",
            sa.SmallInteger(),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "catalog_revision",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.CheckConstraint(
            "id = 1",
            name="ck_catalog_state_singleton",
        ),
        sa.CheckConstraint(
            "catalog_revision >= 0",
            name="ck_catalog_state_revision_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        catalog_state,
        [{"id": 1, "catalog_revision": 0}],
    )


def downgrade() -> None:
    op.drop_table("catalog_state")
