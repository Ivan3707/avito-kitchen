"""add unique constraint for cart customer branch

Revision ID: 325d6568c352
Revises: 754da98a2e8b
Create Date: 2026-09-08 19:35:14.409740

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "325d6568c352"
down_revision: Union[str, Sequence[str], None] = "754da98a2e8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_cart_customer_branch",
        "carts",
        ["customer_id", "branch_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_cart_customer_branch",
        "carts",
        type_="unique",
    )
