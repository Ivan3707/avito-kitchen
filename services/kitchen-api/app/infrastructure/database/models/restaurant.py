from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class Restaurant(TimestampMixin, Base):
    __tablename__ = "restaurants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    external_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_snapshot_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        unique=True,
    )

    last_snapshot_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    catalog_revision: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    catalog_checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "catalog_revision IS NULL OR catalog_revision >= 0",
            name="ck_restaurant_catalog_revision_non_negative",
        ),
        CheckConstraint(
            "catalog_checksum IS NULL OR length(catalog_checksum) = 64",
            name="ck_restaurant_catalog_checksum_length",
        ),
        CheckConstraint(
            "(catalog_revision IS NULL) = (catalog_checksum IS NULL)",
            name="ck_restaurant_catalog_state_complete",
        ),
    )
