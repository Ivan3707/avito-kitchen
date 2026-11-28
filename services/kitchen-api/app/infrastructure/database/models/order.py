from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    restaurant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurants.id",
            ondelete="RESTRICT",
        ),
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

    external_order_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    restaurant_order_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    request_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    rejection_code: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_message: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    rejection_menu_item_external_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    rejection_old_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    rejection_current_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "external_order_id",
            name="uq_order_restaurant_external_id",
        ),
        UniqueConstraint(
            "restaurant_id",
            "restaurant_order_id",
            name="uq_order_restaurant_order_id",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_order_status",
        ),
        CheckConstraint(
            "(status = 'confirmed' AND restaurant_order_id IS NOT NULL "
            "AND rejection_code IS NULL AND rejection_message IS NULL) OR "
            "(status = 'rejected' AND restaurant_order_id IS NULL "
            "AND rejection_code IS NOT NULL AND rejection_message IS NOT NULL) OR "
            "(status = 'pending' AND restaurant_order_id IS NULL "
            "AND rejection_code IS NULL AND rejection_message IS NULL)",
            name="ck_order_result_consistency",
        ),
    )
