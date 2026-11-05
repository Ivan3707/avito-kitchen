from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class RestaurantBranch(TimestampMixin, Base):
    __tablename__ = "restaurant_branches"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    external_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    address: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    is_accepting_orders: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "external_id",
            name="uq_restaurant_branch_external_id",
        ),
        CheckConstraint(
            "is_active OR NOT is_accepting_orders",
            name="ck_branch_accepting_requires_active",
        ),
    )
