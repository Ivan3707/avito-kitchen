"""add branch version

Revision ID: b721e1bd23f8
Revises: 325d6568c352
Create Date: 2026-11-07 22:57:06.643777

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b721e1bd23f8"
down_revision: Union[str, Sequence[str], None] = "325d6568c352"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurant_branches",
        sa.Column(
            "branch_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurant_branches", "branch_version")
