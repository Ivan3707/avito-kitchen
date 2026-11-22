"""add branch version check

Revision ID: de185c05ef9f
Revises: b721e1bd23f8
Create Date: 2026-11-07 23:03:19.727783

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de185c05ef9f"
down_revision: Union[str, Sequence[str], None] = "b721e1bd23f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_restaurant_branch_version_positive",
        "restaurant_branches",
        "branch_version >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_restaurant_branch_version_positive",
        "restaurant_branches",
        type_="check",
    )
