from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.database.models.restaurant_branch import (
        RestaurantBranch,
    )
    from app.infrastructure.database.models.restaurant_order_item import (
        RestaurantOrderItem,
    )


class RestaurantOrder(TimestampMixin, Base):
    __tablename__ = "restaurant_orders"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    external_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    branch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurant_branches.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    accepted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    items: Mapped[list["RestaurantOrderItem"]] = relationship(
        "RestaurantOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    branch: Mapped["RestaurantBranch"] = relationship(
        "RestaurantBranch",
    )

    __table_args__ = (
        UniqueConstraint(
            "external_id",
            name="uq_restaurant_order_external_id",
        ),
        CheckConstraint(
            """
            (
                accepted = TRUE
                AND status != 'rejected'
                AND rejection_reason IS NULL
            )
            OR
            (
                accepted = FALSE
                AND status = 'rejected'
                AND rejection_reason IS NOT NULL
            )
            """,
            name="ck_restaurant_order_result_consistency",
        ),
        CheckConstraint(
            "status IN ('accepted', 'rejected', 'preparing', 'ready', 'completed', 'cancelled')",
            name="ck_restaurant_order_status",
        ),
    )