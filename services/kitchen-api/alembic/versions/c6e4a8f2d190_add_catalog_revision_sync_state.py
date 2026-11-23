"""add catalog revision synchronization state

Revision ID: c6e4a8f2d190
Revises: 8f3c1a7d2e40
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c6e4a8f2d190"
down_revision: Union[str, Sequence[str], None] = "8f3c1a7d2e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column("catalog_revision", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "restaurants",
        sa.Column("catalog_checksum", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_restaurant_catalog_revision_non_negative",
        "restaurants",
        "catalog_revision IS NULL OR catalog_revision >= 0",
    )
    op.create_check_constraint(
        "ck_restaurant_catalog_checksum_length",
        "restaurants",
        "catalog_checksum IS NULL OR length(catalog_checksum) = 64",
    )
    op.create_check_constraint(
        "ck_restaurant_catalog_state_complete",
        "restaurants",
        "(catalog_revision IS NULL) = (catalog_checksum IS NULL)",
    )

    op.add_column(
        "sync_snapshots",
        sa.Column("catalog_revision", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "sync_snapshots",
        sa.Column("catalog_checksum", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "sync_snapshots",
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_sync_snapshot_catalog_revision_non_negative",
        "sync_snapshots",
        "catalog_revision IS NULL OR catalog_revision >= 0",
    )
    op.create_check_constraint(
        "ck_sync_snapshot_catalog_checksum_length",
        "sync_snapshots",
        "catalog_checksum IS NULL OR length(catalog_checksum) = 64",
    )
    op.create_check_constraint(
        "ck_sync_snapshot_catalog_state_complete",
        "sync_snapshots",
        "(catalog_revision IS NULL) = (catalog_checksum IS NULL)",
    )
    op.create_index(
        "ix_sync_snapshots_restaurant_processed_at",
        "sync_snapshots",
        ["restaurant_id", "processed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sync_snapshots_restaurant_processed_at",
        table_name="sync_snapshots",
    )
    op.drop_constraint(
        "ck_sync_snapshot_catalog_state_complete",
        "sync_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_sync_snapshot_catalog_checksum_length",
        "sync_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_sync_snapshot_catalog_revision_non_negative",
        "sync_snapshots",
        type_="check",
    )
    op.drop_column("sync_snapshots", "processed_at")
    op.drop_column("sync_snapshots", "catalog_checksum")
    op.drop_column("sync_snapshots", "catalog_revision")

    op.drop_constraint(
        "ck_restaurant_catalog_state_complete",
        "restaurants",
        type_="check",
    )
    op.drop_constraint(
        "ck_restaurant_catalog_checksum_length",
        "restaurants",
        type_="check",
    )
    op.drop_constraint(
        "ck_restaurant_catalog_revision_non_negative",
        "restaurants",
        type_="check",
    )
    op.drop_column("restaurants", "catalog_checksum")
    op.drop_column("restaurants", "catalog_revision")
