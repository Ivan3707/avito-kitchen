from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, utc_now


class SyncSnapshot(Base):
    __tablename__ = "sync_snapshots"

    snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    restaurant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    catalog_revision: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    catalog_checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "catalog_revision IS NULL OR catalog_revision >= 0",
            name="ck_sync_snapshot_catalog_revision_non_negative",
        ),
        CheckConstraint(
            "catalog_checksum IS NULL OR length(catalog_checksum) = 64",
            name="ck_sync_snapshot_catalog_checksum_length",
        ),
        CheckConstraint(
            "(catalog_revision IS NULL) = (catalog_checksum IS NULL)",
            name="ck_sync_snapshot_catalog_state_complete",
        ),
        Index(
            "ix_sync_snapshots_restaurant_processed_at",
            "restaurant_id",
            "processed_at",
        ),
    )
